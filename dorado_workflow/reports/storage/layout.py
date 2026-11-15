"""Organize user-facing reports and their retained supporting data."""
from html import escape
from pathlib import Path
from urllib.parse import quote
import json
from dataclasses import asdict
import os
import tempfile
import re

SAVED_REPORTS_MARKER = '<!--nanotel-saved-reports-->'


def atomic_text(path, text):
    """Replace a generated file only after its full content is written.

    Args:
        path: File or directory path.
        text: Text to parse, display or write.

    Returns:
        None.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def organize_supporting_data(root):
    """Move native barcode data beneath one folder without merging or overwriting."""
    root = Path(root).resolve()
    destination = root / 'supporting_data'
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError('Invalid supporting-data directory')
    moves = []
    for folder in root.glob('barcode*'):
        if not folder.is_dir() or not re.fullmatch(r'barcode\d+', folder.name, re.I):
            continue
        target = destination / folder.name
        if (folder.is_symlink() or not folder.resolve().is_relative_to(root)
                or not target.resolve().is_relative_to(root)):
            raise ValueError('Barcode data path leaves the NanoTel directory')
        if target.exists():
            raise FileExistsError(f'Supporting data already exists: {target}')
        moves.append((folder, target))
    if moves:
        destination.mkdir(exist_ok=True)
        for folder, target in moves:
            folder.rename(target)


def organize_barcode_reports(root):
    """Move human-facing reports into subfolders; keep pipeline inputs in place.

    Preflight all paths and conflicts before moving anything. Existing identical
    copies can be consolidated; differing files are never silently overwritten.
    Plot HTML and its companion JSON/PNG stay together for relative links.

    Args:
        root: Root directory or root data object for this operation.

    Returns:
        None.
    """
    root = Path(root).resolve()
    moves = []
    from dorado_workflow.utils.source_discovery import barcode_directories
    for folder in barcode_directories(root):
        if not folder.is_dir() or not re.fullmatch(r'barcode\d+', folder.name, re.I):
            continue
        for source in [*folder.iterdir(), *folder.glob('plots/*.plotly.json'), *folder.glob('summaries/*_results.txt')]:
            if not source.is_file():
                continue
            name = source.name
            category = ('report_details' if name.startswith(folder.name + '_telomere_') and name.endswith('.plotly.json') else 'plots' if name.startswith(folder.name + '_telomere_') and
                        (source.suffix.lower() in ('.html', '.png') or name.endswith('.plotly.json'))
                        else '' if name == folder.name + '_results.txt' else None)
            if category is None or (category == '' and source.parent == folder):
                continue
            target = folder / category / name
            if not source.resolve().is_relative_to(root) or not target.resolve().is_relative_to(root):
                raise ValueError('Report path leaves NanoTel directory')
            if target.exists() and (not target.is_file() or source.read_bytes() != target.read_bytes()):
                raise FileExistsError(f'Conflicting report already exists: {target}')
            moves.append((source, target))
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            source.unlink()  # Identical bytes verified above; keep one source.
        else:
            source.rename(target)


def report_index(root):
    """Link existing per-barcode reports without copying or moving source data.

    Args:
        root: Root directory or root data object for this operation.

    Returns:
        HTML linking the saved human-facing barcode reports.
    """
    sections = []
    from dorado_workflow.utils.source_discovery import barcode_directories
    for folder in barcode_directories(root):
        if not folder.is_dir() or not folder.resolve().is_relative_to(root.resolve()):
            continue
        links = []
        # Only human-facing reports belong in the index; intermediate density,
        # motif and coverage exports remain under each barcode/report_details.
        for path in sorted([*folder.glob('*'), *folder.glob('plots/*'), *folder.glob('summaries/*')]):
            if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                continue
            if path.suffix.lower() not in ('.html', '.png', '.txt', '.xlsx'):
                continue
            if path.name.endswith(('_reads_ids.txt', '_results.txt')) or '_telomere_' in path.name:
                continue
            url = quote(path.relative_to(root).as_posix(), safe='/')
            links.append(f'<li><a href="{url}">{escape(path.relative_to(folder).as_posix())}</a></li>')
        sections.append(f'<section><h2>{escape(folder.name)}</h2><ul>{"".join(links)}</ul></section>')
    return ('<details class="note saved-barcode-reports"><summary>Saved barcode reports</summary>'
            + ''.join(sections) + '</details>')


def prepare_run_report(root, run, page):
    """Prepare a self-contained dashboard document without writing or removing files.

    Args:
        root: Root directory or root data object for this operation.
        run: Imported run model containing barcodes, reads and source evidence.
        page: Rendered HTML document.

    Returns:
        Destination path and complete HTML document ready for atomic publication.
    """
    root = Path(root).resolve()
    from ..shared.report_identity import dashboard_filename
    destination = root / dashboard_filename(run.label)
    # Raw per-window/per-hit tracks already live in scientific exports. Duplicating
    # them here can make the HTML gigabytes large, even though charts use aggregates.
    manifest = dict(schema_version=run.schema_version, run_id=run.id,
                    sources=[asdict(source) for source in run.sources],
                    barcodes=[dict(id=b.id, label=b.label) for b in run.barcodes])
    snapshot = json.dumps(manifest, ensure_ascii=True).replace('<', '\\u003c')
    saved_reports = report_index(root)
    if SAVED_REPORTS_MARKER in page:
        page = page.replace(SAVED_REPORTS_MARKER, saved_reports, 1)
        saved_reports = ''
    # Export scripts contain HTML templates with their own </body> strings.
    # Insert only at the document's final closing body, never inside templates.
    before, closing, after = page.rpartition('</body>')
    if not closing:
        raise ValueError('Dashboard document has no closing body tag')
    page = (before + saved_reports + '<script type="application/json" id="source-data">'
            + snapshot + '</script>' + closing + after)
    return destination, page


def write_run_reports(root, run, page):
    """Save a dashboard atomically; source cleanup belongs to the workflow."""
    destination, document = prepare_run_report(root, run, page)
    atomic_text(destination, document)
    return destination
