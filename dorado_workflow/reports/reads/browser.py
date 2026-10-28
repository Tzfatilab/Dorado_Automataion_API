"""Offline read browser over the exported post-filtered population.

Search hits are not base coverage or TVR blocks, so those unsupported columns
remain unavailable until the scientific outputs supply their definitions.
"""
import json
from html import escape
from collections import Counter
from dorado_workflow.reports.shared.colors import motif_color
from pathlib import Path
from dorado_workflow.reports.reads.density import read_track_data, READ_TRACK_SCRIPT


def read_rows(barcode, include_unfiltered=False, plot_folder=None, include_tracks=False):
    """Join exported length records to reads without changing their population."""
    population = barcode.metrics.get('filtered_length_records')
    available = population and population.status == 'available'
    if not available and not include_unfiltered:
        return None
    records = list(population.value) if available else []
    retained = {record['read_id'] for record in records}
    if include_unfiltered:
        records.extend(dict(read_id=read.id, original_id=read.original_id, length_bp=None)
                       for read in barcode.reads if read.id not in retained)
    reads = {read.id: read for read in barcode.reads}
    rows = []
    for record in records:
        read = reads.get(record.get('read_id'))
        length = read.metrics.get('read_length') if read else None
        serial = read.metrics.get('read_number') if read else None
        # Use saved numbers, never a page index that changes with filtering.
        label = (f'Read {int(serial.value)}' if serial and serial.status == 'available'
                 else record['original_id'].split()[0])
        chromosomes, arms = set(), set()
        if read and read.alignments.status == 'available':
            # Retain multiple source assignments; never invent a chromosome arm.
            for alignment in read.alignments.value:
                for key, target in [('chromosome', chromosomes), ('arm', arms)]:
                    fact = alignment.get(key)
                    if fact and fact.status == 'available':
                        target.add(str(fact.value))
        def measurement(key):
            fact = read.metrics.get(key) if read else None
            return fact.value if fact and fact.status == 'available' else None
        # Show exported motif evidence even when an older coverage file cannot
        # support percentages for the expanded interval. Counts are not coverage.
        motif_counts = None
        track = read.tracks.get('motifs') if read else None
        interval = read.calls.get('tvr_inclusive', {}).get('interval') if read else None
        if (track and interval and track.status == 'available' and interval.status == 'available'
                and 'tvr_inclusive' in track.value['methods']):
            counts = Counter(hit['motif'] for hit in track.value['matches']
                if hit['method'] == 'tvr_inclusive' and hit['role'] == 'tvr'
                and hit['end'] > interval.value['start'] and hit['start'] < interval.value['end'])
            motif_counts = [dict(motif=motif, count=count, color=motif_color(motif))
                            for motif, count in sorted(counts.items())]
        regions = read.tracks.get('tvr_regions') if read else None
        def call_length(method):
            fact = read.calls.get(method, {}).get('reported_length') if read else None
            return fact.value if fact and fact.status == 'available' else None
        def call_density(method):
            fact = read.calls.get(method, {}).get('density') if read else None
            return fact.value if fact and fact.status == 'available' else None
        rows.append(dict(source_note=('Saved NanoTel read details. This read is outside the displayed filtered population and is excluded from filtered summary statistics.' if include_unfiltered and record['read_id'] not in retained else None), motifs=motif_counts, exact_length=call_length('exact'), mismatch_length=call_length('mismatch'), exact_density=call_density('exact'), mismatch_density=call_density('mismatch'), tvr_length=call_length('tvr_inclusive'), regions=regions.value if regions and regions.status == 'available' else None, canonical=measurement('canonical_pct'), tvr=measurement('tvr_pct'),
                         blocks=measurement('tvr_block_count'), overlap=measurement('repeat_overlap_bp'),
                         unassigned=measurement('repeat_unassigned_bp'), id=read.id if read else None,
                         header=read.original_id if read else record['original_id'],
                         label=label,
                         telomere=record['length_bp'],
                         length=length.value if length and length.status == 'available' else None,
                         chromosomes=sorted(chromosomes), arms=sorted(arms)))
        if include_tracks:
            rows[-1]['track_data'] = read_track_data(read, plot_folder)
    return rows


def saved_completeness(folder):
    """Recover legacy statuses only for the verified final-histogram population.

    A zero unknown count plus the exhaustive censored list identifies complete
    reads, but only after IDs and all counts agree with the final summary.
    """
    import csv
    import re
    from html import unescape
    if folder is None:
        return {}
    folder = Path(folder)
    summary = folder / (folder.name + '_filtered_sorted_summary.csv')
    figure = folder / 'report_details' / (folder.name + '_telomere_histogram.plotly.json')
    if not summary.is_file() or not figure.is_file():
        return {}
    try:
        plot = json.loads(figure.read_text(encoding='utf-8'))
        title = plot.get('layout', {}).get('title', {})
        title = title.get('text', '') if isinstance(title, dict) else str(title)
        count = re.search(r'Final-filtered reads.*?complete: (\d+) \| censored: (\d+) \| unknown: (\d+)', title)
        if not count or int(count[3]) != 0:
            return {}
        with summary.open(encoding='utf-8-sig', newline='') as stream:
            records = list(csv.DictReader(stream))
        ids = [row['sequence_ID'] for row in records]
        censored = {unescape(header) for trace in plot.get('data', [])
                    if trace.get('name') == 'Censored reads (observed lengths)'
                    for header in trace.get('text', [])}
        complete_count, censored_count = int(count[1]), int(count[2])
        if (len(set(ids)) != len(ids) or len(ids) != complete_count + censored_count
                or len(censored) != censored_count or not censored.issubset(set(ids))):
            return {}
        return {header: 'censored' if header in censored else 'complete' for header in ids}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def saved_filter_reasons(folder):
    """Join explicitly exported NanoTel reasons; reject ambiguous source IDs."""
    import csv
    if folder is None:
        return {}
    folder = Path(folder)
    path = folder / 'report_details' / (folder.name + '_filter_reasons.csv')
    if not path.is_file():
        return {}
    reasons = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for record in csv.DictReader(stream):
            header, reason = record.get('sequence_ID'), record.get('reason')
            if header and reason:
                reasons[header] = None if header in reasons else reason
    return reasons


def reads_section(barcode, results_root=None, show_completeness=True):
    """Embed JSON safely; the browser inserts all source text with textContent."""
    folder = None
    if results_root is not None:
        root = Path(results_root)
        candidates = [root / 'nanotel' / barcode.label, root / barcode.label, root]
        folder = next((p for p in candidates if p.name == barcode.label and p.is_dir()), None)
    rows = read_rows(barcode, plot_folder=folder, include_tracks=True)
    # Serial numbers belong to the source read, including reads excluded from
    # the table's population. Never substitute plot rank for the original number.
    table_ids = {row['id'] for row in rows or []}
    extra_rows = [row for row in read_rows(barcode, include_unfiltered=True) if row['id'] not in table_ids]
    # Add heavy image/track payloads only once per source read.
    by_id = {read.id: read for read in barcode.reads}
    for row in extra_rows:
        row['track_data'] = read_track_data(by_id.get(row['id']), folder)
    # Keep images/coordinates out of the searchable table payload. Only the
    # selected read's track JSON is parsed, rather than every image at startup.
    completeness = saved_completeness(folder) if show_completeness else {}
    filter_reasons = saved_filter_reasons(folder)
    track_scripts = []
    for row in (rows or []) + extra_rows:
        row['completeness'] = completeness.get(row['header'])
        row['nanotel_filter_reason'] = filter_reasons.get(row['header'])
        data = row.pop('track_data', None)
        if data is not None:
            encoded = json.dumps(data, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c')
            track_scripts.append('<script type="application/json" id="read-tracks-' +
                escape(row['id'], quote=True) + '">' + encoded + '</script>')
    payload = json.dumps(rows, ensure_ascii=True).replace('<', '\\u003c')
    extra_payload = json.dumps(extra_rows, ensure_ascii=True).replace('<', '\\u003c')
    labels = {}
    for read in barcode.reads:
        serial = read.metrics.get('read_number')
        if serial and serial.status == 'available':
            labels[read.original_id] = f'Read {int(serial.value)}'
    label_payload = json.dumps(labels, ensure_ascii=True).replace('<', '\\u003c')

    return '''<section class="read-browser"><div class="reads-toolbar">
<h2><span class="number">8</span>Reads <small class="read-total"></small></h2>
<div class="read-controls"><label>Search <input class="read-search" type="search" placeholder="Search reads..."></label><label>Show <select class="read-limit"><option>10</option><option>25</option><option>50</option><option>100</option></select></label>
</div></div><p class="note">Post-filtered telomeric reads. Canonical/TVR percentages use unique matched bases within the TVR-inclusive telomere interval. Categories may overlap; they need not sum to 100%. TVR blocks merge adjacent or overlapping TVR hits. Missing exports remain unavailable.</p>
<div class="reads-scroll"><table class="reads-table"><thead><tr><th>Read number</th><th>Status</th><th>Telomere length (kb)</th><th>Including TVRs (kb)</th><th>Total read length (kb)</th><th>Canonical %</th><th>TVR %</th><th># TVR blocks</th><th>Chromosome</th></tr></thead><tbody></tbody></table></div>
<p class="read-status" role="status"></p><nav class="read-pagination" aria-label="Read pages"></nav>
<script type="application/json" class="read-data">''' + payload + '</script><script type="application/json" class="read-labels">' + label_payload + '</script><script type="application/json" class="read-details">' + extra_payload + '</script>' + ''.join(track_scripts) + '</section>'


# Browser code is packaged separately but embedded for offline navigation.
READ_REPEAT_SCRIPT = '<script>\n' + (Path(__file__).parents[1] / 'assets' / 'read_repeats.js').read_text(encoding='utf-8') + '\n</script>'
READ_SCRIPT = READ_TRACK_SCRIPT + READ_REPEAT_SCRIPT + '<script>\n' + (Path(__file__).parents[1] / 'assets' / 'read_browser.js').read_text(encoding='utf-8') + '\n</script>'
