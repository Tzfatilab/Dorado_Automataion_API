"""Retain source populations in the unified workbook before removing CSV exports."""
import csv
import json
from pathlib import Path
import re

from openpyxl import load_workbook
from dorado_workflow.utils.source_discovery import source_files


def table_name(filename):
    km = re.fullmatch(r'(barcode\d+)_km_statistics.csv', filename, re.I)
    if km:
        return 'km_' + km[1].lower()
    audit = re.fullmatch(r'(barcode\d+)_filtration_reasons.csv', filename, re.I)
    if audit:
        return 'audit_' + audit[1].lower()
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
    return name in {'NanoTel text outputs', 'NanoTel Statistics', 'Run metadata', 'Barcode source counts',
                    'Read motifs', 'Read repeat summaries', 'Read mappings', 'Barcode figures', 'KM by barcode',
                    'KM run statistics', 'NanoTel analysis facts', 'Report sources'} or bool(
        re.fullmatch(r'(?:(?:filtered|final|audit|km)_)?barcode\d+', name))


def text_outputs(root):
    """Only generator-owned per-barcode text outputs, never arbitrary user files."""
    root = Path(root).resolve()
    for path in source_files(root, '*.txt'):
        match = re.fullmatch(r'(barcode\d+)_(?:reads_ids|results)\.txt', path.name, re.I)
        if match and path.resolve().is_relative_to(root):
            yield path


def retained_text(results_root, filename):
    """Read a retired text report from its verified workbook copy."""
    root = Path(results_root)
    for path in (root / 'nanotel/nanotel_results.xlsx', root / 'nanotel_results.xlsx',
                 root / 'nanotel_summary.xlsx'):
        if not path.is_file():
            continue
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            title = '_source_NanoTel text outputs'
            if title not in book.sheetnames:
                continue
            matches = {}
            for name, part, content in list(book[title].values)[1:]:
                if isinstance(name, str) and Path(name).name == filename:
                    matches.setdefault(name, []).append((part, content or ''))
            if len(matches) == 1:
                parts = sorted(next(iter(matches.values())))
                if [part for part, _ in parts] == list(range(1, len(parts) + 1)):
                    return ''.join(content for _, content in parts)
        finally:
            book.close()
    return ''


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


def retain_source_tables(workbook, results_root, run, check_cancelled=None):
    check_cancelled = check_cancelled or (lambda: None)
    check_cancelled()
    appended = 0
    def retain_row(sheet, row):
        nonlocal appended
        appended += 1
        if appended % 256 == 0:
            check_cancelled()
        append_text(sheet, row)
    root = Path(results_root)
    from ..shared.organism import show_km, km_table
    include_km = show_km(run)
    candidates = [root / 'nanotel/nanotel_results.xlsx', root / 'nanotel_summary.xlsx',
                  root / 'reports/post_analysis_sources/nanotel_summary.xlsx']
    # Prefer native current tables. Preserve workbook-only sources on subsequent builds.
    tables = {}
    text_title = '_source_NanoTel text outputs'
    text_records = {}
    for path in candidates:
        if not path.is_file():
            continue
        previous = load_workbook(path, read_only=True, data_only=True)
        try:
            if text_title in previous.sheetnames:
                for name, part, content in list(previous[text_title].values)[1:]:
                    text_records.setdefault((name, part), content or '')
        finally:
            previous.close()
    for path in text_outputs(root):
        name = path.relative_to(root.resolve()).as_posix()
        text_records = {key: value for key, value in text_records.items() if key[0] != name}
        content = path.read_text(encoding='utf-8-sig')
        for part, offset in enumerate(range(0, max(1, len(content)), 30000), 1):
            text_records[(name, part)] = content[offset:offset + 30000]
    if text_records:
        if text_title in workbook.sheetnames:
            del workbook[text_title]
        sheet = workbook.create_sheet(text_title)
        retain_row(sheet, ['Path', 'Part', 'Text'])
        for (name, part), content in sorted(text_records.items()):
            retain_row(sheet, [name, part, content])
        sheet.sheet_state = 'hidden'
    for path in source_files(root, '*.csv'):
        name = table_name(path.name)
        if name and (include_km or not km_table(name)):
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
                retain_row(sheet, row)
        sheet.sheet_state = 'hidden'
    manifest = root / 'nanotel/report_sources.json'
    if manifest.is_file():
        title = '_source_Report sources'
        if title in workbook.sheetnames:
            del workbook[title]
        sheet = workbook.create_sheet(title)
        retain_row(sheet, ['Barcode', 'Original detail folder'])
        for label, folder in sorted(json.loads(manifest.read_text(encoding='utf-8')).items()):
            retain_row(sheet, [label, folder])
        sheet.sheet_state = 'hidden'
    for path in candidates:
        if not path.is_file():
            continue
        previous = load_workbook(path, read_only=True, data_only=True)
        try:
            for source in previous:
                name = source.title.removeprefix('_source_')
                if not include_km and km_table(name):
                    continue
                if not source.title.startswith('_source_') or not retained_name(name) or source.title in workbook.sheetnames:
                    continue
                sheet = workbook.create_sheet(source.title)
                for row in source.values:
                    retain_row(sheet, row)
                sheet.sheet_state = 'hidden'
        finally:
            previous.close()
    if '_source_Barcode source counts' not in workbook.sheetnames:
        sheet = workbook.create_sheet('_source_Barcode source counts')
        sheet.append(['barcode', 'total_reads', 'detected_telomeric_reads', 'total_read_length_median_bp'])
        for barcode in run.barcodes:
            def value(key):
                fact = barcode.metrics.get(key)
                return fact.value if fact and fact.status == 'available' else None
            sheet.append([barcode.label, value('total_reads'), value('detected_telomeric_reads'),
                          value('total_read_length_median_bp')])
        sheet.sheet_state = 'hidden'
    # Legacy retained count tables predate the all-input read-length median.
    # Carry the imported log/JSON value into the workbook before those original
    # files are unavailable on a later workbook-only recalculation.
    counts = workbook['_source_Barcode source counts']
    headers = [cell.value for cell in counts[1]]
    median_key = 'total_read_length_median_bp'
    if median_key not in headers:
        counts.cell(1, counts.max_column + 1, median_key)
        headers.append(median_key)
    if 'barcode' in headers:
        label_column = headers.index('barcode') + 1
        median_column = headers.index(median_key) + 1
        by_label = {barcode.label: barcode for barcode in run.barcodes}
        for row in range(2, counts.max_row + 1):
            barcode = by_label.get(counts.cell(row, label_column).value)
            fact = barcode.metrics.get(median_key) if barcode else None
            if counts.cell(row, median_column).value is None and fact and fact.status == 'available':
                counts.cell(row, median_column, fact.value)
    if '_source_Run metadata' not in workbook.sheetnames:
        sheet = workbook.create_sheet('_source_Run metadata')
        retain_row(sheet, ['Field', 'Part', 'Value'])
        metadata = {'settings': run.settings.value if run.settings.status == 'available' else {},
                    'organism': run.organism.value if run.organism.status == 'available' else '',
                    'stages': {key: fact.value for key, fact in run.stages.items() if fact.status == 'available'}}
        for key, value in metadata.items():
            encoded = json.dumps(value, ensure_ascii=True)
            for offset in range(0, len(encoded), 30000):
                retain_row(sheet, [key, offset // 30000 + 1, encoded[offset:offset + 30000]])
        sheet.sheet_state = 'hidden'
