"""Automatic scientific workbook accompanying each generated dashboard."""
import json
import math
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..reads.browser import read_rows
from ..shared.short_telomeres import short_cutoff_bp
from ..shared.organism import show_km
from ..shared.barcode_statistics import barcode_key_statistics

MISSING = 'Unavailable'
EMPTY = 'Not applicable'


def value(fact):
    """Available metric value, otherwise the enclosing adapter's missing-value marker.

    Args:
        fact: Value together with its availability and provenance.

    Returns:
        Available metric value, otherwise the enclosing adapter's missing-value marker.
    """
    return fact.value if fact and fact.status == 'available' else MISSING


def numeric(v):
    """True for a finite, nonnegative number; boolean values are rejected.

    Args:
        v: Value to inspect or format.

    Returns:
        True for a finite, nonnegative number; boolean values are rejected.
    """
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def build_dashboard_workbook(run, results_root=None, workbook=None, comparisons=None):
    """Build the shared visible layout, optionally retaining hidden source sheets.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports. Default: None.
        workbook: Existing workbook, when supplied. Default: None.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        Workbook containing barcode summaries, read tables and source facts.
    """
    wb = workbook if workbook is not None else Workbook()
    if workbook is None:
        wb.remove(wb.active)

    next_rows = {}

    def sheet(name, headers):
        """New worksheet with the requested headers and frozen identifying column.

        Args:
            name: Name used for lookup, display or storage.
            headers: Ordered column headings.

        Returns:
            New worksheet with the requested headers and frozen identifying column.
        """
        ws = wb.create_sheet(name)
        ws.append(headers)
        ws.freeze_panes = 'B2'
        next_rows[ws] = 2
        return ws

    def append(ws, row):
        # JSON facts can exceed Excel's per-cell limit. Preserve them in ordered
        # chunks rather than silently truncating scientific values.
        """Worksheet row number used for the appended output record.

        Args:
            ws: Worksheet receiving the exported values.
            row: Source row or output row values.

        Returns:
            Worksheet row number used for the appended output record.
        """
        row_number = next_rows[ws]
        ws.append(row)
        next_rows[ws] += 1
        for column in range(1, len(row) + 1):
            cell = ws.cell(row_number, column)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if isinstance(cell.value, str):
                if len(cell.value) > 32767:
                    raise ValueError('Excel cell limit exceeded; use the chunked source facts sheet')
                # Preserve identifiers and user labels as text, including strings
                # beginning with '=' that Excel would otherwise treat as formulas.
                cell.data_type = 's'
        return row_number

    from ..overview.comparisons import comparison_data
    from ..reads.density import tvr_enabled, mismatch_enabled
    comparisons = comparison_data(run) if comparisons is None else comparisons
    compositions = {row['barcode']: row for row in comparisons['composition']}
    tvr_requested = tvr_enabled(run.settings)
    mismatch_requested = mismatch_enabled(run.settings)
    from ..shared.measurement_statistics import method_statistics, barcode_table_statistics
    methods = [('exact', 'Canonical')]
    if mismatch_requested is True:
        methods.append(('mismatch', 'Including mismatch'))
    if tvr_requested is not False:
        methods.append(('tvr_inclusive', 'Including TVRs (without mismatch)' if mismatch_requested is False else 'Including TVRs (with mismatch)'))
    cutoffs = {short_cutoff_bp(run.settings, barcode) for barcode in run.barcodes}
    cutoff_title = (f"telomere length < {next(iter(cutoffs)):g} bp" if len(cutoffs) == 1 and None not in cutoffs
                    else 'per-barcode cutoff; see Definitions')
    method_fields = [('Median telomere length after filtration (kb)', 'median_bp', 1000),
                     (f'Short telomeres after filtration (%, {cutoff_title})', 'short_percent', 100)]
    summary = sheet('Barcode summary', ['Barcode ID', 'Sample name', 'Total number of reads',
        'Median total read length (kb)', 'Telomeric reads before filtration',
        'Telomeric reads before filtration (%)', 'Median total read length of telomeric reads before filtration (kb)',
        'Number of telomeric reads after filtration',
        *[f'{title} - {label}' for title, _, _ in method_fields for _, label in methods],
        *(['Telomeric reads containing TVRs after filtration (%)'] if tvr_requested is not False else []),
        'Number of chromosome ends'])
    # A shared title spans the enabled methods, with concise subheaders below.
    flat_headers = [cell.value for cell in summary[1]]
    summary.append([None] * len(flat_headers))
    for column, title in enumerate(flat_headers, 1):
        summary.cell(1, column).value = title
        if column <= 8 or column > 8 + 2 * len(methods):
            summary.merge_cells(start_row=1, end_row=2, start_column=column, end_column=column)
    for group_index, (title, _, _) in enumerate(method_fields):
        first = 9 + group_index * len(methods)
        for method_index, (_, label) in enumerate(methods):
            summary.cell(1, first + method_index).value = title if method_index == 0 else None
            summary.cell(2, first + method_index).value = label
        if len(methods) > 1:
            summary.merge_cells(start_row=1, end_row=1, start_column=first, end_column=first + len(methods) - 1)
    summary.freeze_panes = 'C3'
    summary.print_title_rows = '1:2'
    next_rows[summary] = 3
    facts = sheet('Source facts', ['Barcode ID', 'Read ID', 'Field', 'Availability', 'Unit',
        'Population', 'Reason', 'Value part', 'Value', 'Evidence'])
    km_keys = ['km_status', 'km_median_bp', 'km_ci_lower_bp', 'km_ci_upper_bp',
        'km_whole_relative_ci_width_pct', 'km_input_read_count', 'km_complete_read_count',
        'km_censored_read_count', 'km_censoring_rate_pct', 'km_reporting_reason']
    km = sheet('Kaplan-Meier', ['Barcode ID', *km_keys]) if show_km(run) else None

    def fact_rows(barcode, read_id, key, fact):
        """Fact rows.

        Args:
            barcode: Imported Barcode record containing reads, metrics and evidence.
            read_id: Read identifier used for joins or navigation.
            key: Lookup key or field name.
            fact: Value together with its availability and provenance.

        Returns:
            None.
        """
        raw = value(fact)
        if isinstance(raw, (dict, list, tuple)):
            raw = json.dumps(raw, default=lambda x: asdict(x) if is_dataclass(x) else str(x), ensure_ascii=True)
        chunks = [raw[i:i+30000] for i in range(0, len(raw), 30000)] if isinstance(raw, str) and len(raw)>30000 else [raw]
        evidence = json.dumps([asdict(e) for e in fact.evidence], separators=(',', ':'))
        # Evidence lists can also be large; the dedicated Sources sheet retains
        # full provenance, and each evidence chunk receives its own fact row.
        evidence_chunks = [evidence[i:i+30000] for i in range(0, len(evidence), 30000)] or ['']
        for i in range(max(len(chunks), len(evidence_chunks))):
            append(facts, [barcode, read_id, key, str(getattr(fact.status, 'value', fact.status)),
                fact.unit, fact.population, fact.reason, i+1,
                chunks[i] if i<len(chunks) else '', evidence_chunks[i] if i<len(evidence_chunks) else ''])

    for key, fact in {'organism': run.organism, 'settings': run.settings, **run.stages, **run.metrics}.items():
        fact_rows('', '', key, fact)
    for barcode in run.barcodes:
        filtered = read_rows(barcode)
        cutoff = short_cutoff_bp(run.settings, barcode)
        source_count = value(barcode.metrics.get('amount_of_telomeres'))
        cutoffs.add(cutoff)
        motif = compositions.get(barcode.label)
        stats = barcode_key_statistics(barcode, run.settings, comparisons['cells'], motif)
        table_stats = barcode_table_statistics(barcode, run.settings)
        measurements = {method: method_statistics(barcode, run.settings, method, 'after') for method, _ in methods}
        def scaled(v, scale=1):
            return v / scale if numeric(v) else v if v == 'Not requested' else MISSING
        row_number = append(summary, [barcode.label, table_stats['sample_name'], value(barcode.metrics.get('total_reads')),
            scaled(table_stats['total_read_length_median_bp'], 1000), scaled(table_stats['detected_reads']),
            scaled(table_stats['detected_percent'], 100), scaled(table_stats['detected_read_length_median_bp'], 1000),
            source_count,
            *[scaled(measurements[method][key], scale) for _, key, scale in method_fields for method, _ in methods],
            *([scaled(table_stats['tvr_read_percent_after'], 100)] if tvr_requested is not False else []),
            stats['chromosomes'] if stats['chromosomes'] is not None else MISSING])
        for col in (4, 7):
            summary.cell(row_number, col).number_format = '0.000'
        summary.cell(row_number, 6).number_format = '0.00%'
        for index, (_, key, _) in enumerate(method_fields):
            for method_index in range(len(methods)):
                summary.cell(row_number, 9 + index * len(methods) + method_index).number_format = '0.000' if key == 'median_bp' else '0.00%'
        if tvr_requested is not False:
            summary.cell(row_number, 9 + len(method_fields) * len(methods)).number_format = '0.00%'
        def kb(v):
            """Length converted from base pairs to kilobases, or the missing-value marker.

            Args:
                v: Value to inspect or format.

            Returns:
                Length converted from base pairs to kilobases, or the missing-value marker.
            """
            return v/1000 if numeric(v) else MISSING
        def pct(v):
            """Percentage converted to an Excel fraction, or the missing-value marker.

            Args:
                v: Value to inspect or format.

            Returns:
                Percentage converted to an Excel fraction, or the missing-value marker.
            """
            return v/100 if numeric(v) else MISSING
        columns = [('Read number', lambda r:r['label'], None), ('Read ID', lambda r:r['header'], None),
            ('Total read length (kb)', lambda r:kb(r['length']), '0.000'),
            ('Telomere start (bp)', lambda r:r.get('mismatch_start' if mismatch_requested is True else 'canonical_start'), '#,##0'),
            ('Filtration status', lambda r:r['filtration_status'], None),
            ('Filtration reason', lambda r:r.get('filtration_reason'), None),
            ('Canonical telomere length (kb)', lambda r:kb(r['exact_length']), '0.000')]
        if mismatch_requested is True:
            columns += [('Telomere length including mismatch (kb)', lambda r:kb(r['mismatch_length']), '0.000')]
        if tvr_requested is not False:
            columns += [('Telomere length including TVRs (kb)', lambda r:kb(r['tvr_length']), '0.000')]
        columns += [('Canonical repeat density (%)', lambda r:r['exact_density'], '0.00%')]
        if mismatch_requested is True:
            columns += [('Repeat density including mismatch (%)', lambda r:r['mismatch_density'], '0.00%')]
        if tvr_requested is not False:
            columns += [('TVR content (%)', lambda r:pct(r['tvr']), '0.00%'),
                        ('Canonical content (%)', lambda r:pct(r['canonical']), '0.00%'),
                        ('TVR patterns', lambda r:', '.join(r['tvr_patterns']) if r.get('tvr_patterns') is not None else MISSING, None)]
        columns += [('Chromosome', lambda r:', '.join(r['chromosomes']) or MISSING, None),
                    ('Arm', lambda r:', '.join(r['arms']) or MISSING, None)]
        retained_ids = {record['read_id'] for record in barcode.metrics['filtered_length_records'].value} if filtered is not None else set()
        before_filter = list(filtered or []) + read_rows(barcode, include_unfiltered=True, exclude_ids=retained_ids)
        for record in before_filter:
            record['filtration_status'] = ('Passed' if record['id'] in retained_ids else 'Not retained') if filtered is not None else 'Unavailable'
        for name, records in [(barcode.label, before_filter)]:
            barcode_sheet = sheet(name,[c[0] for c in columns])
            for record in records or []:
                values = [column[1](record) for column in columns]
                row_number = append(barcode_sheet, [v if v is not None else MISSING for v in values])
                for i,c in enumerate(columns,1):
                    if c[2] and numeric(barcode_sheet.cell(row_number,i).value):
                        barcode_sheet.cell(row_number,i).number_format=c[2]
        if km is not None:
            reportable = value(barcode.metrics.get('km_status')) == 'reportable'
            append(km, [barcode.label, *[value(barcode.metrics.get(k)) if reportable or k not in
                {'km_median_bp', 'km_ci_lower_bp', 'km_ci_upper_bp'} else MISSING for k in km_keys]])
        for key, fact in barcode.metrics.items():
            fact_rows(barcode.label, '', key, fact)
        for read in barcode.reads:
            for key, fact in read.metrics.items():
                fact_rows(barcode.label, read.original_id, key, fact)
            fact_rows(barcode.label, read.original_id, 'filtering', read.filtering)
            fact_rows(barcode.label, read.original_id, 'alignments', read.alignments)
            for method, calls in read.calls.items():
                for key, fact in calls.items():
                    fact_rows(barcode.label, read.original_id, method+'.'+key, fact)
    sources = sheet('Sources', ['Source ID', 'Path', 'SHA256', 'Format', 'Sheet'])
    for source in run.sources:
        append(sources, [source.id, source.path, source.sha256, source.format, source.sheet])
    definitions = sheet('Definitions', ['Field', 'Definition'])
    cutoff_note = ('Telomere length < '+str(next(iter(cutoffs)))+' bp. ') if len(cutoffs)==1 and None not in cutoffs else 'Per-barcode cutoffs are retained in Source facts. '
    for row in [
        ['Measurement methods', 'Canonical: without mismatch or TVR. Mismatch: recorded canonical mismatch-inclusive call without TVR. TVR: recorded TVR-inclusive call using the run matching settings. Methods share the saved filtered membership; no new filtering or detection is run.'],
        ['Before/after filtration', 'Before uses the complete exported detected population. After uses saved filtered record identities. Medians use measured telomere lengths only; short percentages use those same non-missing lengths as denominator and telomere length strictly below the recorded cutoff. Zero measured telomere lengths have no defined median or percentage.'],
        ['Barcode sheets', 'Barcode summary contains barcode-level Key Statistics. Each barcode sheet combines all imported before-filtration telomeric records with a Filtration status column. These are detected summary records, not necessarily all input reads.'],
        ['After filtering', 'The same exported filtered population used by the dashboard.'],
        ['Short telomeres', cutoff_note+'Telomere length strictly below the recorded cutoff. Each method and population uses its non-missing measured telomere lengths as denominator. Excel stores fractions formatted as percentages.'],
        ['Median telomere length', 'Reported after filtration, separately for each enabled measurement method.'],
        ['TVR-positive reads (%)', 'Percentage of retained telomeric reads containing at least one TVR. The denominator is all retained telomeric reads, not bases. Missing motif evidence is not treated as zero.'],
        ['Total read length medians', 'Median total read length uses all input reads. The telomeric read length median uses detected telomeric reads before filtration. Neither is a median of barcode medians.'],
        *[[f'Short cutoff - {barcode.label}', str(short_cutoff_bp(run.settings, barcode)) + ' bp'] for barcode in run.barcodes if len(cutoffs) != 1],
        ['KM', 'Source-assessed pre-edge KM population; distinct from final-filtered reads. No refitting or pooling of KM medians. Estimates withheld by the source remain unavailable. KM sheet is shown only when KM was explicitly enabled in the recorded settings.'],
        ['Missing values', 'Unavailable is missing/invalid/incomplete information. Not applicable is an undefined statistic for an empty population. Zero remains numeric.'],
        ['Source facts', 'Imported run/barcode/read metrics, calls, filtering and alignments with availability, populations and provenance. Long JSON values and evidence are split into numbered chunks.'],
        ['Scope', 'Automatic snapshot of all imported barcodes. Browser-only renaming/exclusion is not applied to this file. Plot images and density/motif track arrays remain in the dashboard and original scientific exports.'],
    ]:
        append(definitions, row)
    for ws in wb:
        if ws.max_row > 1048576 or ws.max_column > 16384:
            raise ValueError(f'Excel worksheet size limit exceeded: {ws.title}')
        ws.auto_filter.ref = f'A2:{get_column_letter(ws.max_column)}{ws.max_row}' if ws is summary else ws.dimensions
        ws.sheet_view.showGridLines = False
        ws.row_dimensions[1].height = 60 if ws is summary else 48
        if ws is summary:
            ws.row_dimensions[2].height = 42
        for header_row in ws.iter_rows(min_row=1, max_row=2 if ws is summary else 1):
            for c in header_row:
                c.font = Font(bold=True, color='FFFFFFFF')
                c.fill = PatternFill('solid', fgColor='FF18324D')
                c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        for i in range(1, ws.max_column+1):
            ws.column_dimensions[get_column_letter(i)].width = min(44, max(15, len(str(flat_headers[i-1] if ws is summary else ws.cell(1,i).value or ''))+2))
        if ws is summary:
            for column in range(9, 9 + 2 * len(methods)):
                ws.column_dimensions[get_column_letter(column)].width = 26
        if ws is definitions:
            ws.column_dimensions['B'].width = 105
            for row in ws.iter_rows(min_row=2):
                ws.row_dimensions[row[0].row].height = 60
                row[1].alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    wb.move_sheet(summary, offset=-wb.index(summary))
    wb.active = 0
    if results_root is not None:
        from ..storage.analysis_metadata import retain_analysis_sheet
        retain_analysis_sheet(wb, results_root)
        from ..storage.source_tables import retain_source_tables
        retain_source_tables(wb, results_root, run)
    facts.sheet_state = 'hidden'
    return wb


def write_dashboard_workbook(run, destination, results_root=None, comparisons=None):
    """Save imported facts atomically without refitting KM or scientific filters.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        destination: Path where the new output is written.
        results_root: Results directory used to resolve saved scientific exports. Default: None.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        Path to the completed Excel workbook.
    """
    destination = Path(destination)
    wb = build_dashboard_workbook(run, results_root, comparisons=comparisons)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp.xlsx')
    try:
        wb.save(temporary)
        os.replace(temporary, destination)
    finally:
        wb.close()
        temporary.unlink(missing_ok=True)
    return destination
