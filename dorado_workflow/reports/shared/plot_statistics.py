"""Descriptive statistics of the same observations plotted in each group."""
from statistics import mean, median


def add_group_statistics(figure, groups):
    for x, values in groups:
        if not values:
            continue
        figure.add_annotation(x=x, y=1.02, xref='x', yref='paper',
            text=(f'{len(values):,}<br>{mean(values):.2f}'
                  f'<br>{median(values):.2f}'
                  f'<br>{100*sum(v < 2 for v in values)/len(values):.1f}'),
            name='group-statistics', showarrow=False, yanchor='bottom',
            align='center', font=dict(size=12))
    figure.add_annotation(x=0,y=1.02,xref='paper',yref='paper',xanchor='right',xshift=-14,
        yanchor='bottom',text='n<br>Mean (kb)<br>Median (kb)<br>% &lt;2 kb',
        name='group-statistics-labels',showarrow=False,align='right',font=dict(size=12))
    figure.update_layout(height=460, margin=dict(t=88,l=125))
