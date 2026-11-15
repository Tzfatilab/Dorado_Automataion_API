"""Select retained source values before writing them into an output worksheet."""
import json
import re
from ..shared.organism import is_km_field, km_table, without_km


def km_reference(values):
    return any(km_table(str(value)) or re.search(
        r'(?:_km_statistics|km_(?:barcode|run)_statistics)\.csv$', str(value), re.I)
        for value in values)


def km_description(values):
    return any(re.search(r'\bKM\b|Kaplan|censor', str(value), re.I) for value in values)


def export_source_rows(name, rows, include_km, check_cancelled=None):
    """Stream permitted rows/columns, normalizing chunked legacy records once.

    No output worksheet is created or edited here. Input source data remains
    unchanged; KM-enabled exports retain every original value.
    """
    check_cancelled = check_cancelled or (lambda: None)
    name = name.removeprefix('_source_')
    if not include_km and km_table(name):
        return
    iterator = iter(rows)
    headers = next(iterator, None)
    if headers is None:
        return
    if include_km:
        yield headers
        for index, row in enumerate(iterator):
            if index % 256 == 0:
                check_cancelled()
            yield row
        return
    if name in {'Run metadata', 'NanoTel text outputs', 'Barcode figures'}:
        yield headers
        groups = {}
        for index, row in enumerate(iterator):
            if index % 256 == 0:
                check_cancelled()
            *identity, part, value = row
            groups.setdefault(tuple(identity), []).append((part, value or ''))
        for identity, parts in groups.items():
            check_cancelled()
            content = ''.join(value for _, value in sorted(parts))
            if name == 'Run metadata' and identity == ('settings',):
                settings = json.loads(content)
                params = settings.get('nanotel_analysis', settings.get('nanotel', settings))
                params['include_km'] = False
                content = json.dumps(settings, ensure_ascii=True)
            elif name == 'NanoTel text outputs' and str(identity[0]).endswith('_results.txt'):
                content = '\n'.join(line for line in content.splitlines()
                                    if not re.search(r'\bKM\b|Kaplan|censor|(?:in)?complete telomeric reads', line, re.I))
            elif name == 'Barcode figures':
                content = json.dumps(without_km(json.loads(content)), ensure_ascii=True, allow_nan=False)
            for offset in range(0, max(1, len(content)), 30000):
                yield [*identity, offset // 30000 + 1, content[offset:offset + 30000]]
        return
    columns = [i for i, header in enumerate(headers) if not is_km_field(header)]
    field = next((headers.index(key) for key in ('Source field', 'Field') if key in headers), None)
    yield [headers[i] for i in columns]
    for index, row in enumerate(iterator):
        if index % 256 == 0:
            check_cancelled()
        if ((field is not None and is_km_field(row[field] if field < len(row) else None))
                or (name == 'Sources' and km_reference(row))
                or (name == 'Definitions' and km_description(row))):
            continue
        yield row if len(columns) == len(headers) else [
            row[i] if i < len(row) else None for i in columns] + list(row[len(headers):])
