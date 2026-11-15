"""Retain NanoTel analysis metadata in Excel instead of loose final JSON files."""
import json
from pathlib import Path
import re

from openpyxl import load_workbook
from dorado_workflow.utils.source_discovery import source_files

SHEET = 'NanoTel analysis facts'
HEADERS = ['Barcode', 'Source field', 'Value']


def flatten_analysis(record, prefix=''):
    """Flatten a source record using the existing analysis-facts worksheet schema.

    Args:
        record: Original JSON object or one of its nested values.
        prefix: Dot-separated source-field prefix.

    Yields:
        Source-field/value pairs, preserving booleans and explicit missing values.
    """
    if isinstance(record, dict):
        for key, value in record.items():
            yield from flatten_analysis(value, f'{prefix}.{key}' if prefix else key)
    else:
        yield prefix, 'Unavailable' if record is None else json.dumps(record) if isinstance(record, list) else record


def analysis_rows(results_root, include_native=True):
    """Read retained analysis fields, with current native JSON taking precedence.

    Args:
        results_root: Results directory containing NanoTel files and workbooks.
        include_native: Whether to include intermediate analysis JSON files.

    Returns:
        Tuples of row dictionary, source path and source worksheet (None for JSON).
    """
    root = Path(results_root)
    rows = {}
    candidates = [root / 'nanotel/nanotel_results.xlsx', root / 'nanotel_results.xlsx',
                  root / 'nanotel_summary.xlsx',
                  root / 'reports/post_analysis_sources/nanotel_summary.xlsx']
    for path in candidates:
        if not path.is_file():
            continue
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            name = next((name for name in ('_source_' + SHEET, SHEET) if name in book.sheetnames), None)
            if name is None:
                continue
            iterator = iter(book[name].values)
            if list(next(iterator, ())) != HEADERS:
                raise ValueError(f'Invalid analysis metadata columns: {path}')
            seen = set()
            for barcode, field, value in iterator:
                if not isinstance(barcode, str) or not re.fullmatch(r'barcode\d+', barcode) or not isinstance(field, str):
                    raise ValueError(f'Invalid analysis metadata identity: {path}')
                key = (barcode, field)
                if key in seen:
                    raise ValueError(f'Duplicate analysis metadata field: {barcode}/{field}')
                seen.add(key)
                rows.setdefault(key, (dict(zip(HEADERS, (barcode, field, value))), path, name))
        finally:
            book.close()
    if include_native:
        seen = set()
        for path in source_files(root, 'barcode*_analysis.json'):
            barcode = path.name.removesuffix('_analysis.json')
            if not re.fullmatch(r'barcode\d+', barcode):
                continue
            if barcode in seen:
                raise ValueError(f'Duplicate NanoTel analysis JSON: {barcode}')
            seen.add(barcode)
            record = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(record, dict) or record.get('barcode') != barcode:
                raise ValueError(f'Analysis barcode identity mismatch: {path}')
            rows = {key: value for key, value in rows.items() if key[0] != barcode}
            for field, value in flatten_analysis(record):
                rows[(barcode, field)] = (dict(zip(HEADERS, (barcode, field, value))), path, None)
    return list(rows.values())


def retain_analysis_sheet(workbook, results_root, include_km=False, check_cancelled=None):
    """Add hidden original analysis fields to an existing output workbook.

    Args:
        workbook: Workbook being built before its atomic save.
        results_root: Directory containing the current or previously retained metadata.

    Returns:
        None; writes only a hidden worksheet, preserving scientific field values.
    """
    check_cancelled = check_cancelled or (lambda: None)
    check_cancelled()
    rows = analysis_rows(results_root)
    name = '_source_' + SHEET
    if name in workbook.sheetnames:
        del workbook[name]
    if not rows:
        return
    sheet = workbook.create_sheet(name)
    sheet.append(HEADERS)
    for row, _, _ in rows:
        check_cancelled()
        from ..shared.organism import is_km_field
        if not include_km and is_km_field(row['Source field']):
            continue
        sheet.append([row[key] for key in HEADERS])
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = 's'
    sheet.sheet_state = 'hidden'
