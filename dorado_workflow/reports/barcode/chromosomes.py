"""Chromosome distribution summaries from the shared post-filtered aggregates."""
from html import escape
import hashlib


def chromosome_section(cells):
    """Render means, descriptive statistics and quartiles without remapping."""
    heading = '<section><h2><span class="number">7</span>Chromosome Comparison</h2>'
    if not cells:
        return heading + '<p class="note">Unavailable: no unambiguous chromosome mappings for post-filtered reads.</p></section>'
    import plotly.graph_objects as go
    # Natural chromosome ordering keeps chr10 after chr9, with X/Y at the end.
    cells = sorted(cells, key=lambda c: (0, int(c['chromosome'][3:]))
                   if c['chromosome'][3:].isdigit() else (1, c['chromosome']))
    dots = [(index, c, read) for index,c in enumerate(cells) for read in c.get('observations', [])]
    # Deterministic horizontal jitter separates molecules without altering lengths.
    # Numeric tick positions keep each cloud centered on its chromosome.
    x = [index + (int(hashlib.sha256(read['read_id'].encode()).hexdigest()[:8],16)/0xffffffff-.5)*.4
         for index,_,read in dots]
    figure = go.Figure(go.Scatter(
        x=list(range(len(cells))), y=[c['median_kb'] for c in cells],
        mode='markers', name='IQR', marker=dict(color='#174978', size=0, opacity=0),
        error_y=dict(type='data', symmetric=False,
            array=[c['q3_kb']-c['median_kb'] for c in cells],
            arrayminus=[c['median_kb']-c['q1_kb'] for c in cells],
            color='#b8d4f6', thickness=3, width=4),
        customdata=[[c['q1_kb'], c['q3_kb'], c['reads'], c['chromosome']] for c in cells],
        hovertemplate='%{customdata[3]}<br>Median: %{y:.3f} kb<br>25th percentile: %{customdata[0]:.3f} kb'
                      '<br>75th percentile: %{customdata[1]:.3f} kb<br>%{customdata[2]} reads<extra></extra>'))
    figure.add_trace(go.Scatter(x=x, y=[read['length_kb'] for _,_,read in dots],
        mode='markers', name='Individual reads', meta='read-links',
        marker=dict(color='#5996E8',size=6,opacity=.6),
        customdata=[[read['barcode_id'],read['read_id'],escape(read['label']),c['chromosome']] for _,c,read in dots],
        hovertemplate='%{customdata[2]}<br>%{customdata[3]}<br>%{y:.3f} kb<br>Click to open read<extra></extra>'))
    # Draw the summary above the dots so its darker diamond remains legible.
    figure.data = (figure.data[1], figure.data[0])
    from statistics import mean
    figure.add_trace(go.Scatter(x=list(range(len(cells))),
        y=[mean(r['length_kb'] for r in c['observations']) for c in cells],
        mode='markers', name='Mean', marker=dict(color='#174978', size=10, symbol='diamond'),
        hovertemplate='Mean: %{y:.3f} kb<extra></extra>'))
    figure.update_layout(template='plotly_white', height=350,
        margin=dict(l=65,r=20,t=20,b=65), showlegend=False,
        font=dict(family='Segoe UI, Arial', color='#12203c'),
        xaxis=dict(title='Chromosome', tickmode='array', tickvals=list(range(len(cells))),
            ticktext=[c['chromosome'] for c in cells], range=[-.6,len(cells)-.4]),
        yaxis=dict(title='Telomere length (kb)', type='linear', rangemode='tozero'))
    from ..shared.plot_statistics import add_group_statistics
    add_group_statistics(figure, [(i, [r['length_kb'] for r in c['observations']]) for i,c in enumerate(cells)])
    payload = figure.to_json().replace('<', '\\u003c')
    return (heading + '<p class="note">Small blue dots: individual reads (click to open) &middot; Dark diamonds: mean &middot; Light blue intervals: IQR (25th&ndash;75th percentile)</p>'
        '<div class="saved-histogram composition-plot"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        '<p class="note">Post-filtered reads with unambiguous chromosome assignments. '
        'Quartiles use linear interpolation; a single read appears as a dot. '
        + 'Linear length axis.'
        + '</p></section>')
