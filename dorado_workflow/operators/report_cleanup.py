"""Verified cleanup of intermediate report sources, owned by the workflow.

Workbook readers/retention live under reports.storage. This module alone decides
when matching intermediate JSON/CSV/text sources can be removed after publication.
"""
import csv
import json
import re
import warnings
from itertools import zip_longest
from pathlib import Path
from openpyxl import load_workbook
from dorado_workflow.utils.source_discovery import source_files
from dorado_workflow.reports.storage.analysis_metadata import analysis_rows, flatten_analysis
from dorado_workflow.reports.storage.source_tables import table_name, text_outputs


def cleanup_legacy_summary_dashboard(destination):
    """Retire a recognized old Summary entry point after its replacement is saved."""
    destination = Path(destination)
    legacy = destination.parent / 'dashboard_summary.html'
    if legacy != destination and legacy.is_file() and 'data-summary-only="true"' in legacy.read_text(encoding='utf-8'):
        legacy.unlink()


def cleanup_analysis_json(results_root, include_km=False):
    """Remove intermediate JSON only when every field is retained in saved Excel.

    Args:
        results_root: Completed run's results directory; original projects are untouched.

    Returns:
        Number of JSON files removed. Unmatched or changed records are retained.
    """
    root = Path(results_root).resolve()
    saved = {(row['Barcode'], row['Source field']): row['Value']
             for row, _, _ in analysis_rows(root, include_native=False)}
    removed = 0
    for path in source_files(root, 'barcode*_analysis.json'):
        barcode = path.name.removesuffix('_analysis.json')
        if not re.fullmatch(r'barcode\d+', barcode) or not path.parent.resolve().is_relative_to(root):
            continue
        record = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(record, dict) or record.get('barcode') != barcode:
            continue
        fields = list(flatten_analysis(record))
        if not include_km:
            from dorado_workflow.reports.shared.organism import is_km_field
            fields = [(field, value) for field, value in fields if not is_km_field(field)]
        if all((barcode, field) in saved and saved[(barcode, field)] == value for field, value in fields):
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                # A locked or protected source link must not turn successfully
                # saved dashboard/Excel outputs into a failed analysis.
                warnings.warn(f'Reports saved; unable to remove intermediate {path.name}: {exc}', RuntimeWarning)
    return removed


def cleanup_source_tables(results_root, workbook_path):
    """Remove only current CSVs whose complete contents match the saved workbook."""
    book = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        title = '_source_NanoTel text outputs'
        if title in book.sheetnames:
            records = {}
            for name, part, content in list(book[title].values)[1:]:
                records.setdefault(name, []).append((part, content or ''))
            root = Path(results_root).resolve()
            for path in text_outputs(root):
                parts = sorted(records.get(path.relative_to(root).as_posix(), []))
                if (parts and [p for p, _ in parts] == list(range(1, len(parts) + 1))
                        and path.read_text(encoding='utf-8-sig') == ''.join(text for _, text in parts)):
                    try:
                        path.unlink()
                    except OSError as exc:
                        warnings.warn(f'Unified Excel saved; could not remove text output {path}: {exc}')
        for path in source_files(results_root, '*.csv'):
            name = table_name(path.name)
            title = '_source_' + name if name else ''
            if title not in book.sheetnames:
                continue
            with path.open(encoding='utf-8-sig', newline='') as stream:
                matches = True
                for row, saved in zip_longest(csv.reader(stream), book[title].values):
                    if row is None or saved is None or row != ['' if value is None else str(value) for value in saved]:
                        matches = False
                        break
            if matches:
                try:
                    path.unlink()
                except OSError as exc:
                    warnings.warn(f'Unified Excel saved; could not remove source CSV {path}: {exc}')
        staged = Path(results_root) / 'reports/post_analysis_sources/nanotel_summary.xlsx'
        if staged.is_file() and staged.resolve() != Path(workbook_path).resolve():
            previous = load_workbook(staged, read_only=True, data_only=True)
            try:
                safe = True
                for sheet in previous:
                    if not sheet.title.startswith('_source_'):
                        continue
                    if sheet.title not in book.sheetnames:
                        safe = False
                        break
                    for original, saved in zip_longest(sheet.values, book[sheet.title].values):
                        if original != saved:
                            safe = False
                            break
                    if not safe:
                        break
            finally:
                previous.close()
            if safe:
                try:
                    staged.unlink()
                except OSError as exc:
                    warnings.warn(f'Unified Excel saved; could not remove staged source workbook: {exc}')
    finally:
        book.close()
    # Recalculation's finished NanoTel folder exposes only the dashboard and
    # workbook. Keep diagnostic logs/configuration in reports, and leave unknown
    # or nonempty user directories alone. Failed exports never reach this point.
    root = Path(results_root).resolve()
    if not (root / 'reports/post_analysis_source.json').is_file():
        return
    nanotel = root / 'nanotel'
    manifest = nanotel / 'report_sources.json'
    if manifest.is_file():
        from dorado_workflow.reports.storage.saved_sources import _source_folders
        path = Path(workbook_path)
        info = path.stat()
        saved = dict(_source_folders(path, info.st_mtime_ns, info.st_size, True))
        original = {label: Path(folder) for label, folder in json.loads(manifest.read_text(encoding='utf-8')).items()}
        if saved == original:
            manifest.unlink()
    report = nanotel / 'nanotel_analysis_report.txt'
    target = root / 'reports' / report.name
    if report.is_file() and not target.exists():
        report.rename(target)
    for folder in nanotel.glob('barcode*'):
        if (folder.is_dir() and re.fullmatch(r'barcode\d+', folder.name, re.I)
                and folder.resolve().is_relative_to(nanotel.resolve()) and not any(folder.iterdir())):
            try:
                folder.rmdir()
            except OSError as exc:
                warnings.warn(f'Report saved; could not remove empty barcode folder {folder}: {exc}')


def cleanup_legacy_reports(root, page):
    """Retire only recognized duplicate viewers after the new dashboard is saved.

    The caller supplies the exact published document so source-specification
    checks match the file that was successfully written. User files are kept.
    """
    root = Path(root).resolve()
    # The self-contained dashboard has been saved successfully. Delete only
    # known redundant barcode viewers/images with retained source specifications.
    from dorado_workflow.utils.source_discovery import barcode_directories
    for folder in barcode_directories(root):
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
    legacy = [(root/'dashboard.html', 'id="source-data"'),
              (root/'index.html', '<title>NanoTel Reports</title>'),
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
