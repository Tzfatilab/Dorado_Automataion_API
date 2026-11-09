"""Compact per-read motif aggregates, independent of later filter membership."""
import json
from collections import Counter
from .models import Availability as A, Fact, unavailable
from ..reads.density import motif_display_label
from ..barcode.repeats import motif_base_counts


def summarize_tracks(read):
    track = read.tracks.get('motifs')
    interval = read.calls.get('tvr_inclusive', {}).get('interval')
    if not track or track.status != A.AVAILABLE or not interval or interval.status != A.AVAILABLE:
        return None
    if 'tvr_inclusive' not in track.value.get('methods', []):
        return None
    start, end = interval.value['start'], interval.value['end']
    hits = [h for h in track.value['matches'] if h['method'] == 'tvr_inclusive'
            and h['end'] > start and h['start'] < end]
    return dict(schema_version=1, method='tvr_inclusive', start=start+1, end=end,
        base_counts=dict(motif_base_counts(start, end, ((motif_display_label(h), h['start'], h['end']) for h in hits))),
        match_counts=dict(Counter(motif_display_label(h) for h in hits)),
        tvr_motifs=dict(Counter(h['motif'] for h in hits if h['role'] == 'tvr')))


def validate_summary(data, read):
    interval = read.calls.get('tvr_inclusive', {}).get('interval')
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('method') != 'tvr_inclusive' or not interval or interval.status != A.AVAILABLE
            or (data.get('start'), data.get('end')) != (interval.value['start']+1, interval.value['end'])):
        raise ValueError('incompatible repeat-summary interval')
    for key in ('base_counts', 'match_counts', 'tvr_motifs'):
        if not isinstance(data.get(key), dict) or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in data[key].items()):
            raise ValueError('invalid motif summary counts')
    if sum(data['base_counts'].values()) != data['end']-data['start']+1:
        raise ValueError('motif summary base counts disagree with interval')
    return data


def prepare_repeat_summaries(importer, barcode):
    summary_only = importer.metadata.get('stages', {}).get('summary_only') is True
    table = importer.saved_statistics.get('Read repeat summaries')
    saved = {}
    if table:
        for row, ev in table[1]:
            if row['barcode'] == barcode.label:
                saved.setdefault(row['read_id'], []).append((int(row['Part']), row['Value'], ev))
    for read in barcode.reads:
        exported = read.metrics.get('_repeat_summary_export')
        data, evidence = None, []
        try:
            if exported and exported.status == A.AVAILABLE:
                data, evidence = json.loads(exported.value), exported.evidence
            elif read.id in saved:
                parts = sorted(saved[read.id])
                if [i for i, _, _ in parts] != list(range(1, len(parts)+1)):
                    raise ValueError('duplicate or missing repeat-summary chunks')
                data, evidence = json.loads(''.join(v for _, v, _ in parts)), [parts[0][2]]
            elif summary_only:
                data = summarize_tracks(read)
                evidence = read.tracks.get('motifs').evidence if data is not None else []
            if data is not None:
                read.metrics['repeat_summary'] = Fact(A.AVAILABLE, validate_summary(data, read), evidence=evidence)
        except (ValueError, TypeError, KeyError) as exc:
            read.metrics['repeat_summary'] = unavailable('Invalid compact motif summary', A.INVALID)
            barcode.warnings.append(f'{read.original_id}: {exc}')
        if summary_only:
            read.tracks['motifs'] = unavailable('Summary mode retains motif aggregates, without match coordinates', A.NOT_REQUESTED)
