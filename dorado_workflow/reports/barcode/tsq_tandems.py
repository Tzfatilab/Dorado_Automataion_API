"""TSQ tandem-array distributions from exported hits or compact detector counts."""
from collections import Counter, defaultdict
import json

from ..shared.colors import motif_color
from ..shared.measurement_statistics import population_reads
from ..shared.repeat_categories import tsq_enabled, tsq_pattern, ordinary_tvr_enabled


def tandem_counts(starts, size):
    """Count maximal exact adjacent-copy arrays, resolving overlapping phases once."""
    phases = defaultdict(list)
    for start in sorted(set(starts)):
        phases[start % size].append(start)
    runs = []
    for phase in phases.values():
        beginning = previous = phase[0]
        copies = 1
        for start in phase[1:]:
            if start == previous + size:
                copies += 1
            else:
                if copies >= 2:
                    runs.append((beginning, copies))
                beginning, copies = start, 1
            previous = start
        if copies >= 2:
            runs.append((beginning, copies))
    counts, accepted = Counter(), []
    for start, copies in sorted(runs, key=lambda run: (-run[1], run[0])):
        end = start + copies * size
        if any(start < b and end > a for a, b in accepted):
            continue
        accepted.append((start, end))
        counts[copies] += 1
    return counts


def read_tsq_tandems(read, settings):
    """Return exact TSQ array counts, or None when source evidence is incomplete."""
    pattern = tsq_pattern(settings)
    interval = read.calls.get('tsq_inclusive', {}).get('interval')
    if (not interval or interval.status != 'available') and ordinary_tvr_enabled(settings) is False:
        interval = read.calls.get('tvr_inclusive', {}).get('interval')
    exported = read.metrics.get('tsq_tandem_counts')
    if exported and exported.status == 'available':
        try:
            data = json.loads(exported.value)
            if (not isinstance(data, dict) or data.get('schema_version') != 1
                    or data.get('motif') != pattern or not interval or interval.status != 'available'
                    or (data.get('start'), data.get('end')) != (interval.value['start']+1, interval.value['end'])
                    or not isinstance(data.get('counts'), list)):
                return None
            counts = Counter()
            for item in data['counts']:
                copies, count = item['repeats'], item['count']
                if type(copies) is not int or copies < 2 or type(count) is not int or count < 1 or copies in counts:
                    return None
                counts[copies] = count
            if sum(copies*count for copies, count in counts.items())*len(pattern) > data['end']-data['start']+1:
                return None
            return counts
        except (ValueError, TypeError, KeyError):
            return None
    # Legacy Full reports can reconstruct arrays directly from their saved hits.
    # Summary totals alone cannot distinguish adjacent copies from scattered hits.
    track = read.tracks.get('motifs')
    if track and track.status == 'available' and interval and interval.status == 'available' and 'tvr_inclusive' in track.value.get('methods', []):
        lo, hi = interval.value['start'], interval.value['end']
        starts = []
        for hit in track.value['matches']:
            if hit['method'] != 'tvr_inclusive' or hit['role'] != 'tvr' or hit['motif'] != pattern:
                continue
            observed = hit.get('matched_sequence')
            if observed is None:
                return None
            if observed == pattern and hit['end']-hit['start'] == len(pattern) and lo <= hit['start'] and hit['end'] <= hi:
                starts.append(hit['start'])
        return tandem_counts(starts, len(pattern))
    summary = read.metrics.get('repeat_summary')
    if summary and summary.status == 'available' and not summary.value['tvr_motifs'].get(pattern, 0):
        return Counter()
    return None


def tsq_tandem_section(barcode, settings):
    """One barcode, all retained telomeric reads in the denominator, including TSQ-negative reads."""
    if tsq_enabled(settings) is not True:
        return ''
    heading = '<section class="tsq-tandem-section"><h2><span class="number">9</span>TSQ Tandem Repeat Distribution</h2>'
    reads = population_reads(barcode, 'after')
    if reads is None:
        return heading + '<p class="note">Unavailable: the after-filtration read population was not exported.</p></section>'
    if not reads:
        return heading + '<p class="note">No telomeric reads after filtration.</p></section>'
    counts, missing = Counter(), 0
    for read in reads:
        values = read_tsq_tandems(read, settings) if read is not None else None
        if values is None:
            missing += 1
        else:
            counts.update(values)
    if missing:
        return heading + (f'<p class="note">Unavailable: TSQ tandem-array data are missing for {missing:,} of {len(reads):,} '
            'after-filtration reads. Older Summary exports do not retain adjacency information; rerun NanoTel to collect compact tandem counts.</p></section>')
    import plotly.graph_objects as go
    x = sorted({2, *counts})
    figure = go.Figure(go.Bar(x=x, y=[counts[n]/len(reads) for n in x], name='TSQ', width=.7,
        marker=dict(color=motif_color('TSQ')), customdata=[[counts[n], len(reads)] for n in x],
        hovertemplate='TSQ tandem repeats: %{x}\u00d7<br>Arrays: %{customdata[0]:,}<br>Telomeric reads: %{customdata[1]:,}<br>Average per read: %{y:.4f}<extra>TSQ</extra>'))
    figure.update_layout(template='plotly_white', height=410, showlegend=True, bargap=.25,
        margin=dict(l=75, r=25, t=45, b=65), font=dict(family='Segoe UI, Arial', color='#12203c'),
        legend=dict(orientation='h', x=.5, xanchor='center', y=1.12),
        xaxis=dict(title='Number of tandem TSQ repeats', ticksuffix='\u00d7', range=[1.5, max(x)+.5],
                   **({'dtick': 1} if max(x) <= 40 else {})),
        yaxis=dict(title='Average number per read', rangemode='tozero',
                   **({'range': [0, 1]} if not counts else {})))
    if not counts:
        figure.add_annotation(text='No TSQ tandem arrays of 2 or more repeats', x=.5, y=.5,
                              xref='paper', yref='paper', showarrow=False)
    payload = figure.to_json().replace('<', '\\u003c')
    return (heading + '<div class="saved-histogram tsq-tandem-plot" style="height:410px"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        f'<p class="note">After filtering. Each bar counts maximal uninterrupted arrays of exact TSQ copies inside the TSQ-inclusive telomere, '
        f'divided by all {len(reads):,} retained telomeric reads, including reads without TSQ. '
        'A 3\u00d7 array counts once at 3\u00d7; isolated copies and partial boundary copies are omitted.</p></section>')
