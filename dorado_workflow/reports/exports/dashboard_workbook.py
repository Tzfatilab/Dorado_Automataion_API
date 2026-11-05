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
            if isinstance(cell.value, str):
                if len(cell.value) > 32767:
                    raise ValueError('Excel cell limit exceeded; use the chunked source facts sheet')
                # Preserve identifiers and user labels as text, including strings
                # beginning with '=' that Excel would otherwise treat as formulas.
                cell.data_type = 's'
        return row_number

    from ..overview.comparisons import comparison_data
    from ..reads.density import tvr_enabled, mismatch_enabled
    from ..shared.barcode_statistics import mismatch_statistics
    comparisons = comparison_data(run) if comparisons is None else comparisons
    compositions = {row['barcode']: row for row in comparisons['composition']}
    tvr_requested = tvr_enabled(run.settings)
    mismatch_requested = mismatch_enabled(run.settings)
    mismatch_mode = tvr_requested is False and mismatch_requested is True
    mismatch_rows = {row['barcode']: row for row in comparisons.get('mismatch_composition', [])}
    summary = sheet('Barcode summary', ['Barcode ID', 'Total barcode reads',
        'Post-filtered telomeric reads', 'Median length (kb)',
        'Reads with mismatches' if mismatch_mode else 'Reads with TVRs',
        'Mismatch patterns' if mismatch_mode else 'TVR motifs',
        'Chromosomes', 'Short telomeres (%)'])
    cutoffs = set()
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
        complete = filtered is not None and all(numeric(r['telomere']) for r in filtered) and (
            not numeric(source_count) or source_count == len(filtered))
        lengths = [r['telomere'] for r in filtered] if complete else None
        short = sum(n<cutoff for n in lengths) if lengths is not None and cutoff is not None else MISSING
        cutoffs.add(cutoff)
        motif = compositions.get(barcode.label)
        no_reads = source_count == 0
        stats = barcode_key_statistics(barcode, run.settings, comparisons['cells'], motif)
        with_tvr = stats['reads_with_tvr'] if stats['reads_with_tvr'] is not None else MISSING
        motif_count = stats['tvr_motifs'] if stats['tvr_motifs'] is not None else MISSING
        if mismatch_mode:
            mismatch_stats = mismatch_statistics(barcode, mismatch_rows.get(barcode.label))
            with_tvr = mismatch_stats['reads_with_mismatch']
            motif_count = mismatch_stats['mismatch_patterns']
            with_tvr = with_tvr if with_tvr is not None else MISSING
            motif_count = motif_count if motif_count is not None else MISSING
        median = stats['median_length_bp']
        append(summary, [barcode.label, value(barcode.metrics.get('total_reads')), source_count,
            EMPTY if no_reads else median/1000 if numeric(median) else MISSING,
            with_tvr, motif_count, stats['chromosomes'] if stats['chromosomes'] is not None else MISSING,
            100*short/len(lengths) if numeric(short) and lengths else EMPTY if lengths == [] else MISSING])
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
            ('Exact telomere length (kb)', lambda r:kb(r['exact_length']), '0.000')]
        columns += [('Exact repeat density (%)', lambda r:r['exact_density'], '0.00%')]
        if mismatch_requested is True:
            columns += [('Telomere length (1 mismatch, kb)',lambda r:kb(r['mismatch_length']),'0.000'),
                        ('Repeat density (1 mismatch, %)',lambda r:r['mismatch_density'],'0.00%')]
        if tvr_requested is False:
            if mismatch_requested is not True:
                columns += [('Filtered telomere length (kb)',lambda r:kb(r['telomere']),'0.000'),
                            ('TVR analysis',lambda r:'Not requested',None)]
            columns += [('Read length (bp)',lambda r:r['length'],'#,##0')]
        else:
            columns += [('Telomere length with TVRs (kb)',lambda r:kb(r['tvr_length']),'0.000'),
                ('TVR content (%)',lambda r:pct(r['tvr']),'0.00%'),
                ('Canonical content (%)',lambda r:pct(r['canonical']),'0.00%'),
                ('TVR blocks',lambda r:r['blocks'],'#,##0')]
        columns += [('Mapping',lambda r:', '.join(r['chromosomes']) or MISSING,None)]
        retained_ids = {record['read_id'] for record in barcode.metrics['filtered_length_records'].value} if filtered is not None else set()
        before_filter = list(filtered or []) + read_rows(barcode, include_unfiltered=True, exclude_ids=retained_ids)
        for name, records in [(barcode.label,filtered),
                              (barcode.label+'_before_filter',before_filter)]:
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
    cutoff_note = ('Length < '+str(next(iter(cutoffs)))+' bp. ') if len(cutoffs)==1 and None not in cutoffs else 'Per-barcode cutoffs are retained in Source facts. '
    for row in [
        ['Barcode sheets', 'Barcode summary contains barcode-level Key Statistics. Each barcode sheet lists the read-level Key Statistics of individual retained reads. Before-filter sheets also include other imported NanoTel summary reads, not necessarily all input reads.'],
        ['After filtering', 'The same exported filtered population used by the dashboard.'],
        ['Short telomeres', cutoff_note+'Length strictly below the recorded cutoff. Denominator: all exported post-filtered reads. Percent values are 0 to 100.'],
        ['Median read length', 'Total read length among exported post-filtered reads, not all input reads. Missing any read length makes this unavailable.'],
        ['KM', 'Source-assessed pre-edge KM population; distinct from final-filtered reads. No refitting or pooling of KM medians. Estimates withheld by the source remain unavailable. KM sheet is shown for explicitly non-human runs.'],
        ['Missing values', 'Unavailable is missing/invalid/incomplete information. Not applicable is an undefined statistic for an empty population. Zero remains numeric.'],
        ['Source facts', 'Imported run/barcode/read metrics, calls, filtering and alignments with availability, populations and provenance. Long JSON values and evidence are split into numbered chunks.'],
        ['Scope', 'Automatic snapshot of all imported barcodes. Browser-only renaming/exclusion is not applied to this file. Plot images and density/motif track arrays remain in the dashboard and original scientific exports.'],
    ]:
        append(definitions, row)
    for ws in wb:
        if ws.max_row > 1048576 or ws.max_column > 16384:
            raise ValueError(f'Excel worksheet size limit exceeded: {ws.title}')
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.showGridLines = False
        ws.row_dimensions[1].height = 48
        for c in ws[1]:
            c.font = Font(bold=True, color='FFFFFF')
            c.fill = PatternFill('solid', fgColor='18324D')
            c.alignment = Alignment(wrap_text=True, vertical='center')
        for i in range(1, ws.max_column+1):
            ws.column_dimensions[get_column_letter(i)].width = min(44, max(15, len(str(ws.cell(1,i).value or ''))+2))
        if ws is definitions:
            ws.column_dimensions['B'].width = 105
            for row in ws.iter_rows(min_row=2):
                ws.row_dimensions[row[0].row].height = 60
                row[1].alignment = Alignment(wrap_text=True, vertical='top')
    wb.move_sheet(summary, offset=-wb.index(summary))
    wb.active = 0
    if results_root is not None:
        from ..storage.analysis_metadata import retain_analysis_sheet
        retain_analysis_sheet(wb, results_root)
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
