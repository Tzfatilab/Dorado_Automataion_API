"""Organized output entry points; scientific source artifacts stay in place."""
from html import escape
from pathlib import Path
from urllib.parse import quote
import json
import os
import tempfile
import re
import warnings


def atomic_text(path, text):
    """Replace a generated file only after its full content is written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def organize_barcode_reports(root):
    """Move human-facing reports into subfolders; keep pipeline inputs in place.

    Preflight all paths and conflicts before moving anything. Existing identical
    copies can be consolidated; differing files are never silently overwritten.
    Plot HTML and its companion JSON/PNG stay together for relative links.
    """
    root = Path(root).resolve()
    moves = []
    for folder in sorted(root.glob('barcode*')):
        if not folder.is_dir() or not re.fullmatch(r'barcode\d+', folder.name, re.I):
            continue
        for source in [*folder.iterdir(), *folder.glob('plots/*.plotly.json')]:
            if not source.is_file():
                continue
            name = source.name
            category = ('report_details' if name.startswith(folder.name + '_telomere_') and name.endswith('.plotly.json') else 'plots' if name.startswith(folder.name + '_telomere_') and
                        (source.suffix.lower() in ('.html', '.png') or name.endswith('.plotly.json'))
                        else 'summaries' if name == folder.name + '_results.txt' else None)
            if category is None:
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
    """Link existing per-barcode reports without copying or moving source data."""
    sections = []
    for folder in sorted(root.glob('barcode*')):
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
            if path.name.endswith('_reads_ids.txt') or '_telomere_' in path.name:
                continue
            url = quote(path.relative_to(root).as_posix(), safe='/')
            links.append(f'<li><a href="{url}">{escape(path.relative_to(folder).as_posix())}</a></li>')
        sections.append(f'<section><h2>{escape(folder.name)}</h2><ul>{"".join(links)}</ul></section>')
    return ('<details class="note"><summary>Saved barcode reports</summary>'
            + ''.join(sections) + '</details>')


def write_run_reports(root, run, page):
    """Write one self-contained dashboard, with embedded source provenance."""
    root = Path(root).resolve()
    destination = root/'dashboard.html'
    snapshot = json.dumps(run.to_dict(), ensure_ascii=True).replace('<', '\\u003c')
    page = page.replace('</main>', report_index(root) + '</main>')
    page = page.replace('</body>', '<script type="application/json" id="source-data">' + snapshot + '</script></body>')
    atomic_text(destination, page)
    # The self-contained dashboard has been saved successfully. Delete only
    # known redundant barcode viewers/images with retained source specifications.
    for folder in root.glob('barcode*'):
        for plot in folder.glob('plots/*'):
            match = re.fullmatch(re.escape(folder.name) + r'_telomere_(plot|histogram)(?:_pct)?\.(html|png)', plot.name)
            if match and (folder.name+'_telomere_'+match[1]+'.plotly.json') in page and plot.resolve().is_relative_to(root) and (folder/'report_details'/(folder.name+'_telomere_'+match[1]+'.plotly.json')).is_file():
                plot.unlink()
        plots = folder/'plots'
        if plots.is_dir() and plots.resolve().is_relative_to(root) and not any(plots.iterdir()):
            try:
                plots.rmdir()
            except PermissionError:
                pass  # Windows can temporarily retain a directory handle.

    # Retire only recognized generator-owned entry points, after the new file
    # exists. Never recursively delete a directory that may contain user files.
    legacy = [(root/'index.html', '<title>NanoTel Reports</title>'),
              (root/'all_barcodes.html', '<title>NanoTel dashboard</title>'),
              (root/'dashboard'/'index.html', 'Telomere Analysis Summary')]
    old_folder = root/'dashboard'
    owned_folder = (old_folder/'index.html').is_file() and 'Telomere Analysis Summary' in (old_folder/'index.html').read_text(encoding='utf-8')
    for path, marker in legacy:
        if path.resolve().is_relative_to(root) and path.is_file() and marker in path.read_text(encoding='utf-8'):
            path.unlink()
    old_snapshot = old_folder/'source-data.json'
    if owned_folder and old_snapshot.resolve().is_relative_to(root) and old_snapshot.is_file():
        old_snapshot.unlink()
    if old_folder.is_dir() and old_folder.resolve().is_relative_to(root) and not any(old_folder.iterdir()):
        try:
            old_folder.rmdir()
        except PermissionError:
            warnings.warn(f'Dashboard saved, but Windows prevented removal of empty folder: {old_folder}', RuntimeWarning)
    return destination
