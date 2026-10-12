"""Barcode motif composition using the existing report match aggregates."""
from html import escape
from .motif_colors import motif_color


def composition_section(row):
    """Show match composition and read prevalence as separately labeled measures.

    A read can contain multiple motifs: read frequencies cannot form a pie.
    The donut therefore uses the exported-match denominator, while
    the center uses the existing count of unique reads containing TVRs.
    """
    heading = '<section><h2><span class="number">5</span>TVR Composition</h2>'
    if row is None:
        return heading + '<p class="note">Unavailable: complete motif exports are required for all post-filtered reads.</p></section>'
    total = sum(row['match_counts'].values())
    if not total:
        return heading + '<p class="note">No exported motif matches inside these TVR-inclusive telomere intervals. Composition percentages are undefined.</p></section>'

    import plotly.graph_objects as go
    labels = sorted(row['match_counts'], key=lambda label: (not label.endswith(' (canonical)'), label))
    # Match the visual reference, while retaining actual source motif names
    # (including reverse-strand canonical patterns) instead of renaming them.
    colors = [motif_color(label) for label in labels]
    counts = [row['match_counts'][label] for label in labels]
    names = [escape(label) for label in labels]
    figure = go.Figure()
    figure.add_trace(go.Pie(labels=names, values=counts, hole=.7, sort=False,
        marker=dict(colors=colors), textinfo='none', domain=dict(x=[0,.72], y=[0,1]),
        hovertemplate='%{label}<br>%{percent} of exported matches<br>%{value} matches<extra></extra>'))
    prevalence = 100 * row['with_tvr'] / row['total']
    figure.update_layout(template='plotly_white', height=max(350, 45 * len(labels)),
        margin=dict(l=20, r=20, t=15, b=20),
        font=dict(family='Segoe UI, Arial', color='#12203c'),
        legend=dict(x=.76, y=.5, yanchor='middle'),
        annotations=[dict(x=.36, y=.5, xref='paper', yref='paper', showarrow=False,
            text=f'Reads with TVRs<br><b>{prevalence:.1f}%</b><br>{row["with_tvr"]:,} / {row["total"]:,} reads',
            font=dict(size=15))])
    payload = figure.to_json().replace('<', '\\u003c')
    return (heading + '<p class="note">Motif composition overlapping TVR-inclusive telomeres of post-filtered reads</p>'
        '<div class="saved-histogram composition-plot"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        '<p class="note">Donut slices: share of exported motif matches, with overlaps retained. '
        'Center: percentage of post-filtered reads containing at least one TVR. These are different measures.</p></section>')
