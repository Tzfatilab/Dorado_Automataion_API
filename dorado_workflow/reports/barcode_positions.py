"""Barcode rug plot of source-exported motif positions overlapping TVR-inclusive telomeres."""
from html import escape
from .motif_colors import motif_color


def positions_section(row):
    """Render source matches already selected by the shared comparison adapter.

    Each tick is one match start, pooled across reads. The analyzed sequence
    orientation is not known to establish distal/proximal biological direction.
    """
    heading = '<section><h2><span class="number">6</span>TVR Position Along Telomeres</h2>'
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
            colorscale='Blues',colorbar=dict(title='Matches'),
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
        margin=dict(l=130,r=25,t=15,b=65),font=dict(family='Segoe UI, Arial',color='#12203c'),
        xaxis=dict(title='Relative position within TVR-inclusive telomere (analyzed sequence start → end)',range=[0,100],dtick=20,ticksuffix='%'),
        yaxis=dict(categoryorder='array',categoryarray=[escape(label) for label in labels],autorange='reversed'))
    payload=figure.to_json().replace('<','\\u003c')
    display_note = ('Dense view: all matches grouped into 0.5% position bins; color shows match count. ' if dense else 'Each tick marks one exported match start, clipped to the telomere boundary when the match crosses it. ')
    return (heading + '<div class="saved-histogram composition-plot"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        f'<p class="note">{display_note}Positions are pooled across post-filtered reads and normalized to each TVR-inclusive telomere interval. '
        'Overlapping matches are retained. Canonical repeats are shown for context. Distal/proximal orientation is not established by these exports.</p></section>')
