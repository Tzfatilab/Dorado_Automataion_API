"""Barcode composition by unique bases within exported telomere intervals."""
from collections import Counter, defaultdict
from html import escape
from dorado_workflow.reports.shared.colors import motif_color


def motif_base_counts(start, end, hits):
    """Partition bases once, matching the read dashboard's interval sweep."""
    events = defaultdict(Counter)
    events[start]; events[end]
    for label, a, b in hits:
        a, b = max(start, a), min(end, b)
        if b > a:
            events[a][label] += 1
            events[b][label] -= 1
    counts, active = Counter(), Counter()
    previous = start
    for position in sorted(events):
        label = ('Unassigned bases' if not active else
                 next(iter(active)) if len(active) == 1 else 'Overlapping motifs')
        counts[label] += position - previous
        active.update(events[position])
        active = +active
        previous = position
    return counts


def composition_section(row, number=5, title="TVR Composition", requested=None):
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
        return '&lt;0.1%' if 0 < 100*value/total < .1 else f'{100*value/total:.1f}%'
    legend = ''.join(f'<li><span class="motif-swatch" style="background:{color}"></span><span>{escape(label)}</span><strong>{percent(value)}</strong></li>' for label,color,value in zip(labels,colors,values))
    return (heading + '<p class="note">Base composition within TVR-inclusive telomeres of post-filtered reads</p>'
        '<div class="read-composition-layout"><div><div class="saved-histogram composition-plot" style="height:350px"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script></div>'
        f'<ul class="read-composition-legend">{legend}</ul></div>'
        '<p class="note">Slices and legend: percentage of pooled telomere bases, counted once. '
        'Unmatched bases are unassigned; bases matching different motifs form an overlap slice. '
        'Center: percentage of reads containing TVRs.</p></section>')
