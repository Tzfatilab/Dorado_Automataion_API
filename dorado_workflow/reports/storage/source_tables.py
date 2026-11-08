"""Retain source populations in the unified workbook before removing CSV exports."""
import csv
import json
from pathlib import Path
import re
import warnings
from itertools import zip_longest

from openpyxl import load_workbook
from dorado_workflow.utils.source_discovery import source_files


def table_name(filename):
    if filename in {'km_barcode_statistics.csv', 'km_run_statistics.csv'}:
        return 'KM by barcode' if filename == 'km_barcode_statistics.csv' else 'KM run statistics'
    match = re.fullmatch(r'(barcode\d+)_summary.csv', filename, re.I)
    if match:
        return match[1].lower()
    match = re.fullmatch(r'filtered_summary(barcode\d+).csv', filename, re.I)
    if match:
        return 'filtered_' + match[1].lower()
    if filename == 'nanotel_summary_statistics.csv':
        return 'NanoTel Statistics'
    # NanoTel's own final-filter population remains separate from R filtration.
    match = re.fullmatch(r'(barcode\d+)_filtered_sorted_summary.csv', filename, re.I)
    return 'final_' + match[1].lower() if match else None


def retained_name(name):
    return name in {'NanoTel Statistics', 'Run metadata', 'Barcode source counts',
                    'Read motifs', 'Read mappings', 'Barcode figures', 'KM by barcode',
                    'KM run statistics', 'NanoTel analysis facts', 'Report sources'} or bool(
        re.fullmatch(r'(?:(?:filtered|final)_)?barcode\d+', name))


def append_text(sheet, row):
    for value in row:
        if isinstance(value, str) and len(value) > 32767:
            raise ValueError('Source value exceeds the Excel cell limit; source CSVs were retained')
    sheet.append(list(row))
    row_number = getattr(sheet, '_retained_row_count', 0) + 1
    sheet._retained_row_count = row_number
    for column in range(1, len(row) + 1):
        cell = sheet.cell(row_number, column)
        if isinstance(cell.value, str):
            cell.data_type = 's'


def retain_source_tables(workbook, results_root, run):
    root = Path(results_root)
    candidates = [root / 'nanotel/nanotel_results.xlsx', root / 'nanotel_summary.xlsx',
                  root / 'reports/post_analysis_sources/nanotel_summary.xlsx']
    # Prefer native current tables. Preserve workbook-only sources on subsequent builds.
    tables = {}
    for path in source_files(root, '*.csv'):
        name = table_name(path.name)
        if name:
            if name in tables:
                raise ValueError('Duplicate source table: ' + name)
            tables[name] = path
    for name, path in tables.items():
        title = '_source_' + name
        if title in workbook.sheetnames:
            continue
        sheet = workbook.create_sheet(title)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.reader(stream):
                append_text(sheet, row)
        sheet.sheet_state = 'hidden'
    manifest = root / 'nanotel/report_sources.json'
    if manifest.is_file():
        title = '_source_Report sources'
        if title in workbook.sheetnames:
            del workbook[title]
        sheet = workbook.create_sheet(title)
        append_text(sheet, ['Barcode', 'Original detail folder'])
        for label, folder in sorted(json.loads(manifest.read_text(encoding='utf-8')).items()):
            append_text(sheet, [label, folder])
        sheet.sheet_state = 'hidden'
    for path in candidates:
        if not path.is_file():
            continue
        previous = load_workbook(path, read_only=True, data_only=True)
        try:
            for source in previous:
                name = source.title.removeprefix('_source_')
                if not source.title.startswith('_source_') or not retained_name(name) or source.title in workbook.sheetnames:
                    continue
                sheet = workbook.create_sheet(source.title)
                for row in source.values:
                    append_text(sheet, row)
                sheet.sheet_state = 'hidden'
        finally:
            previous.close()
    if '_source_Barcode source counts' not in workbook.sheetnames:
        sheet = workbook.create_sheet('_source_Barcode source counts')
        sheet.append(['barcode', 'total_reads', 'detected_telomeric_reads'])
        for barcode in run.barcodes:
            def value(key):
                fact = barcode.metrics.get(key)
                return fact.value if fact and fact.status == 'available' else None
            sheet.append([barcode.label, value('total_reads'), value('detected_telomeric_reads')])
        sheet.sheet_state = 'hidden'
    if '_source_Run metadata' not in workbook.sheetnames:
        sheet = workbook.create_sheet('_source_Run metadata')
        append_text(sheet, ['Field', 'Part', 'Value'])
        metadata = {'settings': run.settings.value if run.settings.status == 'available' else {},
                    'organism': run.organism.value if run.organism.status == 'available' else '',
                    'stages': {key: fact.value for key, fact in run.stages.items() if fact.status == 'available'}}
        for key, value in metadata.items():
            encoded = json.dumps(value, ensure_ascii=True)
            for offset in range(0, len(encoded), 30000):
                append_text(sheet, [key, offset // 30000 + 1, encoded[offset:offset + 30000]])
        sheet.sheet_state = 'hidden'


def cleanup_source_tables(results_root, workbook_path):
    """Remove only current CSVs whose complete contents match the saved workbook."""
    book = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
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
        from .saved_sources import _source_folders
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
