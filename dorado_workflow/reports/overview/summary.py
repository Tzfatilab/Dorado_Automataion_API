"""Small offline overview for summary-only runs; no read tracks or read pages."""
import json
from html import escape
from pathlib import Path

from ..reads.browser import read_rows
from ..shared.organism import show_km
from ..shared.short_telomeres import short_statistics, pooled_short_statistics
from ..storage.layout import atomic_text


def render_summary(run):
    import plotly.graph_objects as go
    from plotly.offline import plot

    def val(entity, key):
        fact = entity.metrics.get(key)
        return fact.value if fact and fact.status == 'available' else None

    def display(v, unit=''):
        return 'Unavailable' if v is None else escape(f'{v:,.3f}'.rstrip('0').rstrip('.')+unit) if isinstance(v, float) else escape(str(v)+unit)

    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+display(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

    def card(label, v, note=''):
        return '<article><span>'+escape(label)+'</span><strong>'+display(v)+'</strong><small>'+escape(note)+'</small></article>'

    from ..interactive.dashboard import dashboard_data
    from .comparisons import comparison_data
    from ..reads.density import tvr_enabled, mismatch_enabled
    aggregate_metrics = dashboard_data(run)['metrics']
    def aggregate(key):
        fact = aggregate_metrics.get(key, {})
        return fact.get('value') if fact.get('status') == 'available' else None
    comparisons = comparison_data(run)
    composition = {row['barcode']: row for row in comparisons['composition']}
    no_tvr = tvr_enabled(run.settings) is False
    with_mismatch = mismatch_enabled(run.settings) is True
    read_columns = [('Read ID','header',1),('Read number','label',1),('Filter status','filter_status',1),
        ('Filtered telomere length (bp)','telomere',1),('Read length (bp)','length',1),
        ('Exact telomere length (bp)','exact_length',1)]
    if no_tvr:
        read_columns += [('Exact repeat density (%)','exact_density',100)]
        if with_mismatch:
            read_columns += [('1 mismatch telomere length (bp)','mismatch_length',1),
                             ('Repeat density (1 mismatch, %)','mismatch_density',100)]
        else:
            read_columns += [('TVR analysis','tvr_analysis',1)]
    else:
        read_columns += [('Telomere length with TVRs (bp)','tvr_length',1),
                         ('TVR content (%)','tvr',1),('Canonical content (%)','canonical',1),('TVR blocks','blocks',1)]
    read_columns += [('Mapping','mapping',1)]
    facts = [short_statistics(b, run.settings) for b in run.barcodes]
    pooled = pooled_short_statistics(run)
    counts = [val(b,'amount_of_telomeres') for b in run.barcodes]
    exported = [val(b,'filtered_length_records') for b in run.barcodes]
    cards = card('Barcodes',len(run.barcodes))+card('Input reads',aggregate('total_reads'))
    cards += card('Post-filtered telomeric reads',aggregate('telomeric_reads'))
    cards += card('Median telomere length (kb)',aggregate('median_telomere_length')/1000 if aggregate('median_telomere_length') is not None else None,'Pooled exported post-filtered reads')
    cards += card('Short telomeres',f"{pooled['percent']:.1f}%" if pooled['percent'] is not None else None,
        f"Length < {pooled['cutoff_bp']:g} bp; {pooled['numerator']}/{pooled['denominator']} exported post-filtered reads" if pooled['percent'] is not None else 'A recorded cutoff and complete comparable populations are required')
    figures=[]
    violin=go.Figure()
    for b, rows in zip(run.barcodes,exported):
        if rows:
            values=[r['length_bp']/1000 for r in rows]
            varied=len(set(values))>1
            violin.add_trace(go.Violin(name=b.label,y=values,points=False if varied else 'all',bandwidth=1.0 if varied else 0,meanline_visible=False,box_visible=False,spanmode='hard',scalemode='width',pointpos=0,fillcolor='#a6d0f5',line_color='#214e78',marker=dict(color='#3d83c9',size=5)))
    violin.update_layout(title='Telomere Length by Barcode',yaxis_title='Telomere length (kb)',showlegend=False,template='plotly_white')
    cutoffs={f['cutoff_bp'] for f in facts if f['denominator']}
    if len(cutoffs)==1 and None not in cutoffs:
        cutoff=next(iter(cutoffs));violin.add_hline(y=cutoff/1000,line_dash='dash',line_color='#b45309',annotation_text=f'Short: < {cutoff/1000:g} kb')
    figures.append(violin)
    bars=go.Figure(go.Bar(x=[b.label for b,c in zip(run.barcodes,counts) if c is not None],y=[c for c in counts if c is not None]))
    bars.update_layout(title='Post-filtered Reads by Barcode',yaxis_title='Reads',template='plotly_white');figures.append(bars)
    short=go.Figure(go.Bar(x=[b.label for b,f in zip(run.barcodes,facts) if f['percent'] is not None],y=[f['percent'] for f in facts if f['percent'] is not None],
        customdata=[[f['cutoff_bp'],f['numerator'],f['denominator']] for f in facts if f['percent'] is not None],
        hovertemplate='%{x}: %{y:.1f}%<br>Length < %{customdata[0]} bp<br>%{customdata[1]} / %{customdata[2]} post-filtered reads<extra></extra>'))
    short.update_layout(title='Short Telomeres by Barcode',yaxis_title='Short telomeres (%)',template='plotly_white');figures.append(short)
    charts=''.join(plot(f,output_type='div',include_plotlyjs=True if i==0 else False,config={'responsive':True,'displaylogo':False}) for i,f in enumerate(figures))
    summary_rows=[];payload=[]
    for b,f,rows in zip(run.barcodes,facts,exported):
        summary_rows.append([b.label,val(b,'total_reads'),len(read_rows(b,include_unfiltered=True)),len(rows) if rows is not None else None,
            val(b,'median_telomere_length')/1000 if val(b,'median_telomere_length') is not None else None,f['cutoff_bp'],f['numerator'],f['denominator'],f['percent']])
        retained={r['id'] for r in read_rows(b) or []}
        def records(source):
            result=[]
            for r in source or []:
                values={**r,'filter_status':'Retained' if r['id'] in retained else
                    'Outside exported filtered population' if rows is not None else 'Unknown',
                    'mapping':', '.join(r['chromosomes']) or None,'tvr_analysis':'Not requested'}
                result.append([values.get(key)*scale if isinstance(values.get(key),(int,float)) else values.get(key)
                               for _,key,scale in read_columns])
            return result
        motif=composition.get(b.label)
        empty=val(b,'amount_of_telomeres')==0
        chromosomes={c['chromosome'] for c in comparisons['cells'] if c['barcode']==b.label}
        stats={'Total barcode reads':val(b,'total_reads'), 'Post-filtered telomeric reads':val(b,'amount_of_telomeres'),
            'Median length (kb)':val(b,'median_telomere_length')/1000 if val(b,'median_telomere_length') is not None else None,
            'Reads with TVRs':'Not requested' if no_tvr else 0 if empty else motif['with_tvr'] if motif else None,
            'TVR motifs':'Not requested' if no_tvr else 0 if empty else len(motif['motifs']) if motif else None,
            'Chromosomes':len(chromosomes) if chromosomes else 0 if empty else None,'Short telomeres (%)':f['percent']}
        payload.append({'barcode':b.label,'stats':stats,'before':records(read_rows(b,include_unfiltered=True)),
                        'filtered':records(read_rows(b)),'available':rows is not None})
    km=''
    if show_km(run):
        keys=['km_status','km_median_bp','km_ci_lower_bp','km_ci_upper_bp','km_input_read_count','km_complete_read_count','km_censored_read_count','km_censoring_rate_pct','km_reporting_reason']
        kmrows=[]
        for b in run.barcodes:
            reportable=val(b,'km_status')=='reportable'
            kmrows.append([b.label,*[val(b,k) if reportable or k not in {'km_median_bp','km_ci_lower_bp','km_ci_upper_bp'} else None for k in keys]])
        km='<section><h2>Kaplan-Meier estimates</h2><p>Source-assessed pre-edge population. Distinct from post-filtered reads; KM medians are not pooled. Withheld estimates remain unavailable.</p>'+table(['Barcode','Status','KM median (bp)','95% CI lower (bp)','95% CI upper (bp)','KM input reads','Complete reads','Censored reads','Censoring (%)','Reporting reason'],kmrows)+'</section>'
        km+='<section><h2>Final-filter read completeness</h2><p>NanoTel final-filtered population; distinct from the KM input and R post-analysis populations.</p>'+table(['Barcode','Final-filter reads','Complete reads','Incomplete reads','Censoring (%)'],[[b.label,*[val(b,k) for k in ['nanotel_final_number_of_telomeric_reads_post_filtration','nanotel_final_complete_telomeric_reads','nanotel_final_incomplete_telomeric_reads','nanotel_final_censoring_rate_pct']]] for b in run.barcodes])+'</section>'
    headers=[c[0] for c in read_columns]
    encoded=json.dumps(payload,ensure_ascii=True,allow_nan=False).replace('<','\\u003c')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NanoTel Summary Dashboard</title><style>
body{font:15px system-ui,sans-serif;background:#f5f8fc;color:#18324d;margin:24px}main{max-width:1500px;margin:auto}section{background:white;border:1px solid #dbe4ef;border-radius:12px;padding:20px;margin:18px 0}.stats{display:flex;gap:12px;flex-wrap:wrap}article{background:#edf4fc;border-radius:10px;padding:18px;flex:1;min-width:150px}strong,small{display:block}strong{font-size:27px;margin:12px 0}small,p{color:#52657d}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap}th{background:#edf3fb}button,select,input{font:inherit;padding:8px;margin:5px;border:1px solid #c8d6e8;border-radius:6px;background:white}.controls{display:flex;flex-wrap:wrap;align-items:center}a{color:#2456a6}</style><main><h1>NanoTel Summary Dashboard</h1><p>Summary only · Numeric results and read tables. No per-read plots or density/motif tracks.</p><a href="nanotel_summary.xlsx">Open Excel workbook</a><section><h2>Key Statistics — All Barcodes</h2><div class="stats">'''+cards+'</div></section><section>'+charts+'</section><section><h2>Barcode summary</h2>'+table(['Barcode','Input reads','Exported before-filter reads','Exported post-filter reads','Median telomere (kb)','Short cutoff (bp)','Short read count','Short denominator','Short telomeres (%)'],summary_rows)+'</section>'+km+'''<section><h2>Read tables by barcode</h2><p>Before filtering includes imported NanoTel summary reads, not necessarily every input/basecalled read. Missing measurements are unavailable. Table selections do not change the statistics above.</p><div class="controls"><label>Barcode <select id="barcode"></select></label><label>Population <select id="population"><option value="filtered">After filtering</option><option value="before">Before filtering</option></select></label><label>Search <input id="search" type="search"></label></div><h3 id="selected-title">Key Statistics</h3><div class="stats" id="selected-stats"></div><div class="scroll"><table><thead><tr>'''+''.join('<th>'+escape(h)+'</th>' for h in headers)+'''</tr></thead><tbody id="reads"></tbody></table></div><div class="controls"><button id="previous">Previous</button><span id="status" role="status"></span><button id="next">Next</button></div></section><script type="application/json" id="summary-reads">'''+encoded+'''</script><script>
(()=>{const data=JSON.parse(document.getElementById('summary-reads').textContent),byId=id=>document.getElementById(id);let page=0;for(let i=0;i<data.length;i++){const o=document.createElement('option');o.value=i;o.textContent=data[i].barcode;byId('barcode').append(o);}function render(){const entry=data[Number(byId('barcode').value)],population=byId('population').value,q=byId('search').value.toLowerCase();byId('selected-title').textContent='Key Statistics - '+(entry?.barcode||'No barcode');byId('selected-stats').replaceChildren();for(const [label,value] of Object.entries(entry?.stats||{})){const article=document.createElement('article'),span=document.createElement('span'),strong=document.createElement('strong');span.textContent=label;strong.textContent=value==null?'Unavailable':typeof value==='number'?value.toLocaleString(undefined,{maximumFractionDigits:3}):String(value);article.append(span,strong);byId('selected-stats').append(article);}const rows=(entry?.[population]||[]).filter(r=>!q||r.some(v=>v!=null&&String(v).toLowerCase().includes(q)));const pages=Math.max(1,Math.ceil(rows.length/25));page=Math.min(page,pages-1);byId('reads').replaceChildren();for(const row of rows.slice(page*25,page*25+25)){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v==null?'Unavailable':String(v);tr.append(td);}byId('reads').append(tr);}byId('status').textContent=entry&&!entry.available&&population==='filtered'?'Filtered population unavailable':`${rows.length} reads · Page ${page+1} / ${pages}`;byId('previous').disabled=page===0;byId('next').disabled=page>=pages-1;}for(const id of ['barcode','population','search'])byId(id).addEventListener('input',()=>{page=0;render();});byId('previous').onclick=()=>{page--;render();};byId('next').onclick=()=>{page++;render();};render();})();
</script></main></html>'''


def write_summary_dashboard(run, destination):
    destination=Path(destination)
    atomic_text(destination,render_summary(run))
    return destination

