"""Explicit opt-in rules for KM execution and report visibility."""
import re


def km_requested(settings):
    """KM is opt-in for every organism, including Human."""
    return isinstance(settings, dict) and settings.get('include_km') is True


def show_km(run):
    """Show KM only when the saved analysis settings explicitly enable it."""
    if run.settings.status != 'available':
        return False
    settings = run.settings.value
    if not isinstance(settings, dict):
        return False
    params = settings.get('nanotel_analysis', settings.get('nanotel', settings))
    return isinstance(params, dict) and km_requested(params)


def is_km_field(name):
    name = str(name).casefold().removeprefix('nanotel_final_')
    return name.startswith('km_') or name in {
        'event', 'completeness', 'read_completeness', 'complete_telomeric_reads',
        'incomplete_telomeric_reads', 'censoring_rate_pct',
    }


def without_km(value):
    """Omit optional KM/completeness facts from a published copy."""
    if isinstance(value, dict):
        value = {key: without_km(item) for key, item in value.items() if not is_km_field(key)}
        if isinstance(value.get('data'), list) and isinstance(value.get('layout'), dict):
            from ..barcode.length_plots import _hide_completeness
            _hide_completeness(value)
        return value
    if isinstance(value, list):
        return [without_km(item) for item in value]
    return value


def km_table(name):
    name = name.removeprefix('_source_')
    return name in {'Kaplan-Meier', 'KM by barcode', 'KM run statistics'} or bool(re.fullmatch(r'km_barcode\d+', name))


def filter_km_workbook(workbook, enabled):
    """Prevent old source exports and hidden sheets from bypassing the opt-in."""
    if enabled:
        return
    import json
    for sheet in list(workbook):
        if km_table(sheet.title):
            workbook.remove(sheet)
            continue
        name = sheet.title.removeprefix('_source_')
        if name in {'Run metadata', 'NanoTel text outputs'}:
            groups = {}
            for identity, part, value in list(sheet.values)[1:]:
                groups.setdefault(identity, []).append((part, value or ''))
            sheet.delete_rows(2, sheet.max_row)
            for identity, parts in groups.items():
                content = ''.join(value for _, value in sorted(parts))
                if name == 'Run metadata' and identity == 'settings':
                    settings = json.loads(content)
                    params = settings.get('nanotel_analysis', settings.get('nanotel', settings))
                    params['include_km'] = False
                    content = json.dumps(settings, ensure_ascii=True)
                elif name == 'NanoTel text outputs' and str(identity).endswith('_results.txt'):
                    content = '\n'.join(line for line in content.splitlines()
                                        if not re.search(r'\bKM\b|Kaplan|censor|(?:in)?complete telomeric reads', line, re.I))
                for index in range(0, max(1, len(content)), 30000):
                    sheet.append([identity, index // 30000 + 1, content[index:index + 30000]])
            continue
        if name == 'Barcode figures':
            groups = {}
            for barcode, kind, part, value in list(sheet.values)[1:]:
                groups.setdefault((barcode, kind), []).append((part, value))
            sheet.delete_rows(2, sheet.max_row)
            for (barcode, kind), parts in groups.items():
                payload = without_km(json.loads(''.join(value for _, value in sorted(parts))))
                encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False)
                for index in range(0, len(encoded), 30000):
                    sheet.append([barcode, kind, index // 30000 + 1, encoded[index:index + 30000]])
            continue
        headers = [cell.value for cell in sheet[1]]
        field = next((headers.index(key) for key in ('Source field', 'Field') if key in headers), None)
        if field is not None or name in {'Sources', 'Definitions'}:
            # sheet[index] recomputes max_column by scanning every stored cell.
            # Repeating it for every row makes large exports quadratic. Bound
            # the width once and inspect values in one pass instead.
            removed = []
            for index, values in enumerate(sheet.iter_rows(min_row=2, max_col=len(headers), values_only=True), 2):
                if ((field is not None and is_km_field(values[field]))
                        or (name == 'Sources' and any(km_table(str(v)) or re.search(r'(?:_km_statistics|km_(?:barcode|run)_statistics)\.csv$', str(v), re.I) for v in values))
                        or (name == 'Definitions' and any(re.search(r'\bKM\b|Kaplan|censor', str(v), re.I) for v in values))):
                    removed.append(index)
            # Delete consecutive matches together, from the bottom, preserving
            # the order and formatting of all retained records.
            while removed:
                end = start = removed.pop()
                while removed and removed[-1] == start - 1:
                    start = removed.pop()
                sheet.delete_rows(start, end - start + 1)
        for column in range(len(headers), 0, -1):
            if is_km_field(headers[column - 1]):
                sheet.delete_cols(column)
