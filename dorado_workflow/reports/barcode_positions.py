"""Barcode rug plot of source-exported motif positions inside exact telomeres."""
from html import escape


def positions_section(row):
    """Render source matches already selected by the shared comparison adapter.

    Each tick is one match start, pooled across reads. The analyzed sequence
    orientation is not known to establish distal/proximal biological direction.
    """
    heading = '<section><h2><span class="number">5</span>TVR Position Along Telomeres</h2>'
    if row is None:
        return heading + ('<p class="note">Unavailable: this run does not contain complete per-read motif-position exports. '
                          'Summary lengths and density plots cannot reconstruct TVR sequences or positions.</p></section>')
    positions = row.get('positions', [])
    if not positions:
        return heading + '<p class="note">No exported motif matches inside these exact telomere intervals.</p></section>'
    import plotly.graph_objects as go
    labels = sorted({p['motif'] for p in positions}, key=lambda label:(not label.endswith(' (canonical)'),label))
    figure = go.Figure()
    for label in labels:
        hits = [p for p in positions if p['motif'] == label]
        color = ('#5996E8' if label.endswith(' (canonical)') else
                 {'TCAGGG':'#EFA44D','TGAGGG':'#57A76D','TTGGGG':'#E45E5D'}.get(label,'#A180D4'))
        # Retain exact motif names instead of concealing multiple motifs as Other.
        figure.add_trace(go.Scatter(x=[p['percent'] for p in hits], y=[escape(label)]*len(hits),
            mode='markers', name=escape(label), marker=dict(symbol='line-ns',size=20,color=color,
                line=dict(color=color,width=1.5),opacity=.65),
            customdata=[[escape(p['read']),p['start'],p['end']] for p in hits],
            hovertemplate='%{y}<br>%{customdata[0]}<br>Match start: %{x:.2f}% of telomere<br>Read positions: %{customdata[1]}–%{customdata[2]} bp (1-based inclusive)<extra></extra>'))
    figure.update_layout(template='plotly_white',height=max(320,55*len(labels)+110),showlegend=False,
        margin=dict(l=130,r=25,t=15,b=65),font=dict(family='Segoe UI, Arial',color='#12203c'),
        xaxis=dict(title='Relative position within exact telomere (analyzed sequence start → end)',range=[0,100],dtick=20,ticksuffix='%'),
        yaxis=dict(categoryorder='array',categoryarray=[escape(label) for label in labels],autorange='reversed'))
    payload=figure.to_json().replace('<','\\u003c')
    return (heading + '<div class="saved-histogram composition-plot"></div>'
        f'<script type="application/json" class="histogram-figure">{payload}</script>'
        '<p class="note">Each tick marks an exported motif match start, pooled across post-filtered reads and normalized to its exact telomere interval. '
        'Overlapping matches are retained. Canonical repeats are shown for context. Distal/proximal orientation is not established by these exports.</p></section>')
