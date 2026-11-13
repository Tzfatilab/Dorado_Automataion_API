"""Descriptive statistics of the same observations plotted in each group."""
from statistics import mean, median
import heapq
import math


def running_medians(values):
    """Prefix medians in display order, excluding missing values without filling gaps."""
    lower, upper, result = [], [], []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            result.append(None)
            continue
        if not lower or value <= -lower[0]:
            heapq.heappush(lower, -value)
        else:
            heapq.heappush(upper, value)
        if len(lower) > len(upper) + 1:
            heapq.heappush(upper, -heapq.heappop(lower))
        elif len(upper) > len(lower):
            heapq.heappush(lower, -heapq.heappop(upper))
        result.append(-lower[0] if len(lower) > len(upper) else (-lower[0] + upper[0]) / 2)
    return result


def add_group_statistics(figure, groups, *, include_median=True, short_cutoffs=None):
    """Add group statistics.

    Args:
        figure: Plotly figure to annotate or style.
        groups: Plotted group positions paired with their length observations.
        include_median: Whether to include median annotations alongside count and mean. Default: True.
        short_cutoffs: Short-telomere cutoffs keyed by plotted group. Default: None.

    Returns:
        None.
    """
    for x, values in groups:
        if not values:
            continue
        cutoff = short_cutoffs.get(x) if short_cutoffs is not None else None
        short = (f'{100*sum(v < cutoff for v in values)/len(values):.1f}' if cutoff is not None else 'Unavailable')
        figure.add_annotation(x=x, y=1.02, xref='x', yref='paper',
            text=(f'{len(values):,}<br>{mean(values):.2f}'
                  + (f'<br>{median(values):.2f}' if include_median else '')
                  + ('<br>' + short if short_cutoffs is not None else '')),
            name='group-statistics', showarrow=False, yanchor='bottom',
            align='center', font=dict(size=12))
    thresholds = set(short_cutoffs.values()) if short_cutoffs is not None else set()
    short_label = (f'Short (&lt; {next(iter(thresholds)):g} kb), %' if len(thresholds) == 1 and None not in thresholds else 'Short, %')
    figure.add_annotation(x=0,y=1.02,xref='paper',yref='paper',xanchor='right',xshift=-14,
        yanchor='bottom',text='n<br>Mean (kb)' + ('<br>Median (kb)' if include_median else '') + ('<br>' + short_label if short_cutoffs is not None else ''),
        name='group-statistics-labels',showarrow=False,align='right',font=dict(size=12))
    figure.update_layout(height=460, margin=dict(t=88,l=125))
