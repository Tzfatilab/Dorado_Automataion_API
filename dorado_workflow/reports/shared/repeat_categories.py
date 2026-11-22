"""TSQ search identity and disjoint base coverage, separate from ordinary TVRs."""
from ..interactive.models import Fact, Availability as A, unavailable


def repeat_options(settings):
    value = settings.value if settings and settings.status == 'available' else {}
    options = value.get('nanotel_analysis', value) if isinstance(value, dict) else {}
    return options if isinstance(options, dict) else {}


def tsq_pattern(settings):
    return str(repeat_options(settings).get('tsq1_pattern') or 'AACCGC').upper()


def tsq_enabled(settings):
    patterns = repeat_options(settings).get('tvr_patterns')
    return tsq_pattern(settings) in patterns if isinstance(patterns, list) else None


def ordinary_tvr_enabled(settings):
    patterns = repeat_options(settings).get('tvr_patterns')
    return bool(set(patterns) - {tsq_pattern(settings)}) if isinstance(patterns, list) else None


def variants_enabled(settings):
    tsq, tvr = tsq_enabled(settings), ordinary_tvr_enabled(settings)
    return True if tsq is True or tvr is True else False if tsq is False and tvr is False else None


def variant_panel_title(settings):
    if tsq_enabled(settings) is True:
        return 'TSQ patterns' if ordinary_tvr_enabled(settings) is False else 'TVR and TSQ patterns'
    return 'TVR patterns'


def displayed_methods(settings):
    # The combined legacy call remains internal for composition/track coordinates.
    from ..reads.density import mismatch_enabled
    methods = [('exact', 'Canonical')]
    if mismatch_enabled(settings) is True:
        methods.append(('mismatch', '+ Mismatch'))
    if ordinary_tvr_enabled(settings) is not False:
        methods.append(('tvr_inclusive', '+ TVRs'))
    if tsq_enabled(settings) is True:
        methods.append(('tsq_inclusive', '+ TSQ'))
    return methods


def measurement_method(settings, method):
    return 'tvr_only' if method == 'tvr_inclusive' and tsq_enabled(settings) is True else method


def union_length(ranges):
    total = 0
    end = -1
    for a, b in sorted(ranges):
        total += max(0, b - max(a, end))
        end = max(end, b)
    return total


def separate_read_categories(importer, barcode):
    """Retain searched-motif provenance; TSQ bases take precedence over TVR bases.

    Both percentages use the same combined interval, so they never double-count
    each other. Independent telomere boundaries must come from NanoTel exports.
    """
    settings = Fact(A.AVAILABLE, importer.metadata.get('settings', {}))
    pattern = tsq_pattern(settings)
    tsq, tvr = tsq_enabled(settings), ordinary_tvr_enabled(settings)
    for read in barcode.reads:
        evidence = importer.meta_evidence or read.evidence
        read.metrics['tsq_requested'] = Fact(A.AVAILABLE, tsq, evidence=evidence) if tsq is not None else unavailable('TSQ selection not recorded')
        read.metrics['ordinary_tvr_requested'] = Fact(A.AVAILABLE, tvr, evidence=evidence) if tvr is not None else unavailable('TVR selection not recorded')
        read.metrics['tsq_pattern'] = Fact(A.AVAILABLE, pattern, evidence=evidence)
        track = read.tracks.get('motifs')
        if not track or track.status != A.AVAILABLE:
            # New compact exports carry separately validated base counts.
            # Old combined percentages cannot be split without motif coordinates.
            if tsq is True and read.metrics.get('tsq_pct', unavailable('Missing')).status != A.AVAILABLE:
                old = read.metrics.get('tvr_pct')
                if tvr is False and old and old.status == A.AVAILABLE:
                    read.metrics['tsq_pct'] = old
                    read.metrics['tsq_bp'] = read.metrics['tvr_bp']
                    read.metrics['tvr_pct'] = Fact(A.AVAILABLE, 0, unit='%', evidence=old.evidence)
                    read.metrics['tvr_bp'] = Fact(A.AVAILABLE, 0, unit='bp', evidence=old.evidence)
                    read.calls['tsq_inclusive'] = read.calls['tvr_inclusive']
                else:
                    read.metrics['tvr_pct'] = unavailable('Legacy combined coverage cannot separate TSQ and TVRs')
                    read.metrics['tvr_bp'] = unavailable('Legacy combined coverage cannot separate TSQ and TVRs')
            continue
        for hit in track.value['matches']:
            if hit['role'] == 'tvr' and hit['motif'] == pattern:
                hit['category'] = 'tsq'
        interval = read.calls.get('tvr_inclusive', {}).get('interval')
        if not interval or interval.status != A.AVAILABLE or 'tvr_inclusive' not in track.value['methods']:
            continue
        lo, hi = interval.value['start'], interval.value['end']
        tsq_ranges, tvr_ranges = [], []
        for hit in track.value['matches']:
            if hit['method'] != 'tvr_inclusive' or hit['role'] != 'tvr':
                continue
            a, b = max(lo, hit['start']), min(hi, hit['end'])
            if b > a:
                (tsq_ranges if hit.get('category') == 'tsq' else tvr_ranges).append((a, b))
        s, t = union_length(tsq_ranges), union_length(tsq_ranges + tvr_ranges) - union_length(tsq_ranges)
        for prefix, bases in [('tsq', s), ('tvr', t)]:
            for suffix, value, unit in [('bp', bases, 'bp'), ('pct', 100 * bases / (hi - lo), '%')]:
                read.metrics[prefix + '_' + suffix] = Fact(A.AVAILABLE, value, unit=unit,
                    population='disjoint_variant_coverage_combined_interval',
                    origin='presentation_aggregate', evidence=track.evidence)
        if tsq is True and tvr is False:
            read.calls['tsq_inclusive'] = read.calls['tvr_inclusive']


def tsq_read_count(barcode, settings, population='after'):
    from .measurement_statistics import population_reads
    if tsq_enabled(settings) is not True:
        return None
    reads = population_reads(barcode, population)
    if reads is None:
        return None
    count = 0
    for read in reads:
        if read is None:
            return None
        fact = read.metrics.get('tsq_pct')
        if fact and fact.status == A.AVAILABLE:
            count += fact.value > 0
            continue
        compact = read.metrics.get('repeat_summary')
        if compact and compact.status == A.AVAILABLE:
            count += bool(compact.value['tvr_motifs'].get(tsq_pattern(settings)))
        else:
            return None
    return count
