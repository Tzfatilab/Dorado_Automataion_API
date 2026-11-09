"""Statistics over recorded per-read calls, with explicit method and population."""
from statistics import median

from ..reads.density import mismatch_enabled, tvr_enabled
from .short_telomeres import short_cutoff_bp

METHODS = [('exact', 'Without mismatch or TVR'),
           ('mismatch', 'With mismatch, without TVR'),
           ('tvr_inclusive', 'With mismatch and TVR')]


def selected_method(settings):
    return 'mismatch' if mismatch_enabled(settings) is True else 'exact'


def population_reads(barcode, population):
    if population == 'before':
        source = barcode.metrics.get('imported_read_records')
        return barcode.reads if source and source.population == 'detected_summary_records' else None
    source = barcode.metrics.get('filtered_length_records')
    if not source or source.status != 'available':
        return None
    by_id = {read.id: read for read in barcode.reads}
    return [by_id.get(row['read_id']) for row in source.value]


def method_statistics(barcode, settings, method, population):
    requested = (True if method == 'exact' else mismatch_enabled(settings)
                 if method == 'mismatch' else tvr_enabled(settings))
    reads = population_reads(barcode, population)
    values = None
    if requested is not False and reads is not None:
        values = []
        records = barcode.metrics.get('filtered_length_records')
        for index, read in enumerate(reads):
            if population == 'after' and records and records.status == 'available':
                exported = records.value[index].get('method_lengths_bp')
                if exported is not None and method in exported:
                    if exported.get(method) is not None:
                        values.append(exported[method])
                    continue
            length = read.calls.get(method, {}).get('reported_length') if read else None
            if length and length.status == 'available':
                values.append(length.value)
    cutoff = short_cutoff_bp(settings, barcode)
    return dict(requested=requested, lengths=values,
                records=len(reads) if reads is not None else None,
                measured=len(values) if values is not None else None,
                missing=len(reads) - len(values) if reads is not None and values is not None else None,
                median_bp=median(values) if values else None,
                short_percent=100 * sum(n < cutoff for n in values) / len(values)
                    if values and cutoff is not None else None)


def tvr_read_count(barcode, settings, population):
    if tvr_enabled(settings) is False:
        return 'Not requested'
    reads = population_reads(barcode, population)
    if reads is None:
        return None
    count = 0
    for read in reads:
        summary = read.metrics.get('repeat_summary') if read else None
        if summary and summary.status == 'available':
            count += bool(summary.value['tvr_motifs'])
            continue
        motifs = read.tracks.get('motifs') if read else None
        interval = read.calls.get('tvr_inclusive', {}).get('interval') if read else None
        if not motifs or motifs.status != 'available' or 'tvr_inclusive' not in motifs.value['methods']:
            return None
        if not interval or interval.status != 'available':
            return None
        count += any(hit['method'] == 'tvr_inclusive' and hit['role'] == 'tvr'
                     and hit['end'] > interval.value['start'] and hit['start'] < interval.value['end']
                     for hit in motifs.value['matches'])
    return count


def barcode_table_statistics(barcode, settings):
    """Summary populations shared by automatic and browser Excel exports."""
    def metric(key):
        fact = barcode.metrics.get(key)
        return fact.value if fact and fact.status == 'available' else None
    reads = population_reads(barcode, 'before')
    lengths = [read.metrics.get('read_length') for read in reads] if reads is not None else []
    complete = reads is not None and all(f and f.status == 'available' for f in lengths)
    detected = len(reads) if reads is not None else None
    total = metric('total_reads')
    retained = population_reads(barcode, 'after')
    positive = tvr_read_count(barcode, settings, 'after')
    return dict(sample_name=metric('sample_name') or '',
                total_read_length_median_bp=metric('total_read_length_median_bp'),
                detected_reads=detected,
                detected_percent=100 * detected / total if detected is not None and total else None,
                detected_read_length_median_bp=median([f.value for f in lengths]) if complete and lengths else None,
                tvr_read_percent_after=(100 * positive / len(retained)
                    if isinstance(positive, (int, float)) and retained else
                    'Not requested' if positive == 'Not requested' else None))
