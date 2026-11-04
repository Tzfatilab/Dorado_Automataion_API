"""Barcode TVR composition and positions from source-exported motif evidence."""
from collections import Counter, defaultdict
from html import escape
from dorado_workflow.reports.shared.colors import motif_color


def motif_base_counts(start, end, hits):
    """Partition bases once, matching the read dashboard's interval sweep.

    Args:
        start: Interval start in the declared coordinate convention.
        end: Interval end in the declared coordinate convention.
        hits: Exported motif matches; this function does not search sequences.

    Returns:
        Base counts partitioned by motif, overlap and unassigned spans.
    """
    events = defaultdict(Counter)
    events[start]; events[end]
    for label, a, b in hits:
        a, b = max(start, a), min(end, b)
        if b > a:
            events[a][label] += 1
            events[b][label] -= 1
    counts, active = Counter(), Counter()
    previous = start
    # Sweep disjoint spans so overlapping hits do not count the same base twice.
    for position in sorted(events):
        label = ('Unassigned bases' if not active else
                 next(iter(active)) if len(active) == 1 else 'Overlapping motifs')
        counts[label] += position - previous
        active.update(events[position])
        active = +active
        previous = position
    return counts


def composition_section(row, number=5, title="TVR patterns", requested=None):
    """Show base composition in the ring and read prevalence in its center.

    These use different denominators: covered telomere bases versus reads.

    Args:
        row: Source row or output row values.
        number: Number displayed in the report section heading. Default: 5.
        title: Displayed title. Default: 'TVR patterns'.
        requested: Whether the corresponding analysis was explicitly requested. Default: None.

    Returns:
        HTML markup for composition section.
    """
    attribute = ' data-tvr-requested="false"' if requested is False else ''
    heading = f'<section{attribute}><h2><span class="number">{number}</span>{escape(title)}</h2>'
    if requested is False:
        return heading + '<p class="note">Not requested: no TVR patterns were selected for this run.</p></section>'
    if row is None or 'base_counts' not in row:
        return heading + '<p class="note">Unavailable: complete motif exports are required for all post-filtered reads.</p></section>'
    total = sum(row['base_counts'].values())
    if not total:
        return heading + '<p class="note">No positive-length TVR-inclusive intervals are available.</p></section>'
    import plotly.graph_objects as go
    counts = row['base_counts']
    labels = sorted((label for label, count in counts.items() if count or label == 'Unassigned bases'),
        key=lambda label: (label in ('Unassigned bases', 'Overlapping motifs'), not label.endswith(' (canonical)'), label))
    if 'Unassigned bases' not in labels:
        labels.append('Unassigned bases')
    colors = [('#b5bdc7' if label == 'Unassigned bases' else '#806b93' if label == 'Overlapping motifs' else motif_color(label)) for label in labels]
    values = [counts.get(label, 0) for label in labels]
    figure = go.Figure(go.Pie(labels=[escape(label) for label in labels], values=values,
        hole=.7, sort=False, marker=dict(colors=colors), textinfo='none', showlegend=False,
        hovertemplate='%{label}<br>%{percent} of telomere bases<br>%{value:,} bp<extra></extra>'))
    prevalence = 100 * row['with_tvr'] / row['total']
    figure.update_layout(template='plotly_white', height=350, margin=dict(l=10,r=10,t=10,b=10),
        font=dict(family='Segoe UI, Arial', color='#12203c'),
        annotations=[dict(x=.5,y=.5,xref='paper',yref='paper',showarrow=False,
            text=f'Reads with TVRs<br><b>{prevalence:.1f}%</b><br>{row["with_tvr"]:,} / {row["total"]:,} reads',font=dict(size=15))])
    payload = figure.to_json().replace('<', '\\u003c')
    def percent(value):
        """Formatted percentage text, retaining a visible marker for very small positive values.

        Args:
            value: Value to inspect, convert or format.

        Returns:
            Formatted percentage text, retaining a visible marker for very small positive values.
        """
        return '&lt;0.1%' if 0 < 100*value/total < .1 else f'{100*value/total:.1f}%'
    legend = ''.join(f'<li><span class="motif-swatch" style="background:{color}"></span><span>{escape(label)}</span><strong>{percent(value)}</strong></li>' for label,color,value in zip(labels,colors,values))
    return (heading + '<p class="note">Base composition within TVR-inclusive telomeres of post-filtered reads</p>'
        '<div class="read-composition-layout"><div><div class="saved-histogram composition-plot" style="height:350px"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script></div>'
        f'<ul class="read-composition-legend">{legend}</ul></div>'
        '<p class="note">Slices and legend: percentage of pooled telomere bases, counted once. '
        'Unmatched bases are unassigned; bases matching different motifs form an overlap slice. '
        'Center: percentage of reads containing TVRs.</p></section>')


def positions_section(row, requested=None):
    """Render source matches already selected by the shared comparison adapter.

    Each tick is one match start, pooled across reads. The analyzed sequence
    orientation is not known to establish distal/proximal biological direction.

    Args:
        row: Source row or output row values.
        requested: Whether the corresponding analysis was explicitly requested. Default: None.

    Returns:
        HTML markup for positions section.
    """
    heading = '<section><div class="report-section-heading"><h2><span class="number">6</span>TVR Position Along Telomeres</h2></div>'
    if requested is False:
        return heading + '<p class="note">Not requested: no TVR patterns were selected for this run.</p></section>'
    if row is None:
        return heading + ('<p class="note">Unavailable: this run does not contain complete per-read motif-position exports. '
                          'Summary lengths and density plots cannot reconstruct TVR sequences or positions.</p></section>')
    positions = row.get('positions', [])
    if not positions:
        return heading + '<p class="note">No exported motif matches inside these TVR-inclusive telomere intervals.</p></section>'
    import plotly.graph_objects as go
    labels = sorted({p['motif'] for p in positions}, key=lambda label:(not label.endswith(' (canonical)'),label))
    figure = go.Figure()
    dense = len(positions) > 20000
    if dense:
        # Aggregate every source match into 0.5%-wide display bins. No random
        # sampling, motif calling or scientific filtering: counts are conserved.
        bins = 200
        counts = {label: [0]*bins for label in labels}
        for hit in positions:
            counts[hit['motif']][min(bins-1, int(hit['percent']*bins/100))] += 1
        figure.add_trace(go.Heatmap(x=[(i+.5)*100/bins for i in range(bins)],
            y=[escape(label) for label in labels],z=[counts[label] for label in labels],
            colorscale='Blues',colorbar=dict(title=dict(text='Matches',side='top'),
                x=1.02,xanchor='left',thickness=16,len=.9,tickfont=dict(size=12)),
            hovertemplate='%{y}<br>Position bin centered at %{x:.2f}% (width 0.5%)<br>%{z} exported matches<extra></extra>'))
    else:
        for label in labels:
            hits = [p for p in positions if p['motif'] == label]
            color = motif_color(label)
            # Retain exact motif names instead of concealing multiple motifs as Other.
            figure.add_trace(go.Scatter(x=[p['percent'] for p in hits], y=[escape(label)]*len(hits),
                mode='markers', name=escape(label), marker=dict(symbol='line-ns',size=20,color=color,
                    line=dict(color=color,width=1.5),opacity=.65),
                customdata=[[escape(p['read']),p['start'],p['end']] for p in hits],
                hovertemplate='%{y}<br>%{customdata[0]}<br>Match start: %{x:.2f}% of telomere<br>Read positions: %{customdata[1]}–%{customdata[2]} bp (1-based inclusive)<extra></extra>'))
    figure.update_layout(template='plotly_white',height=max(320,55*len(labels)+110),showlegend=False,
        margin=dict(l=180,r=120 if dense else 30,t=45 if dense else 20,b=80,autoexpand=True),font=dict(family='Segoe UI, Arial',color='#12203c'),
        xaxis=dict(title='Relative position within TVR-inclusive telomere (analyzed sequence start → end)',range=[0,100],dtick=20,ticksuffix='%'),
        yaxis=dict(categoryorder='array',categoryarray=[escape(label) for label in labels],autorange='reversed',automargin=True))
    payload=figure.to_json().replace('<','\\u003c')
    display_note = ('Dense view: all matches grouped into 0.5% position bins; color shows match count. ' if dense else 'Each tick marks one exported match start, clipped to the telomere boundary when the match crosses it. ')
    return (heading + '<div class="saved-histogram composition-plot"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        f'<p class="note">{display_note}Positions are pooled across post-filtered reads and normalized to each TVR-inclusive telomere interval. '
        'Overlapping matches are retained. Canonical repeats are shown for context. Distal/proximal orientation is not established by these exports.</p></section>')
