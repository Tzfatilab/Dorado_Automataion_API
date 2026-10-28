/* Length distributions lead; counts/composition share a row; heatmap follows. */
(() => {
  const start=()=>{
    const grid=document.querySelector('#run-overview>.charts');if(!grid)return;
    grid.classList.add('overview-chart-grid');
    let style=document.getElementById('overview-chart-layout');
    if(!style){style=document.createElement('style');style.id='overview-chart-layout';document.head.appendChild(style);}
    style.textContent=`
      .overview-chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:stretch}
      .overview-chart-grid>section{grid-column:auto!important;min-width:0;padding:20px;box-sizing:border-box;display:flex;flex-direction:column}
      .overview-chart-grid>section.overview-full-width{grid-column:1 / -1!important}
      .overview-panel-header{flex:none;margin-bottom:2px}
      .overview-panel-header.has-view-controls{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:20px;row-gap:4px}
      .overview-panel-header.has-view-controls h2{margin:0}
      .overview-panel-header.has-view-controls .overview-panel-actions{justify-self:end;justify-content:flex-end;min-height:0}
      .overview-panel-header.has-view-controls>.graph-export-controls{grid-column:1 / -1}
      .overview-panel-header h2{font-size:21px;line-height:1.3;min-height:56px;margin:0 0 8px;display:flex;align-items:center;gap:12px}
      .overview-panel-header .number{flex-shrink:0;font-size:25px;width:40px;height:40px;line-height:40px}
      .overview-panel-actions{min-height:48px;display:flex;align-items:center;flex-wrap:wrap}
      .overview-panel-actions:empty{display:none}
      .overview-full-width .overview-panel-header h2{min-height:0}
      .overview-panel-actions .barcode-scale-controls{margin:0!important;gap:6px!important}
      .overview-panel-actions button{font-size:13px!important;padding:7px 11px!important}
      .overview-panel-header>.graph-export-controls{min-height:32px;margin:6px 0 0!important}
      .overview-chart-grid .js-plotly-plot{min-width:0;max-width:100%;box-sizing:border-box;margin:0!important}
      .overview-chart-grid>section>p.note:last-child{margin-top:auto;padding-top:12px;font-size:12px;line-height:1.5}
      .overview-chart-grid .read-composition-layout{min-width:0;flex:1;align-items:center}
      .overview-chart-grid .read-composition-legend{min-width:0;padding-left:12px;font-size:13px}
      @media(max-width:1100px){.overview-chart-grid{grid-template-columns:minmax(0,1fr)}.overview-panel-header h2{min-height:0}}
      @media(max-width:1000px){.overview-panel-header.has-view-controls{grid-template-columns:minmax(0,1fr)}.overview-panel-header.has-view-controls .overview-panel-actions{justify-self:start;justify-content:flex-start}}
    `;
    const sections=[...grid.children].filter(n=>n.tagName==='SECTION');
    const specs=[['Telomere Length by Barcode',1,'Telomere Length by Barcode'],
      ['Telomeric Reads by Barcode',2,'Telomeric Reads by Barcode'],['TVR Composition',3,null],
      ['Median Telomere Length by Chromosome',4,'Median Telomere Length by Chromosome']];
    for(const [match,number,title] of specs){
      const section=sections.find(s=>s.querySelector('h2')?.textContent.includes(match));if(!section)continue;
      section.style.gridColumn='auto';section.style.minWidth='0';grid.appendChild(section);
      section.classList.toggle('overview-full-width',number===1||number===4);
      const heading=section.querySelector('h2');
      const text=title||(heading.textContent.includes('Available Barcodes')?'TVR Composition - Available Barcodes':'TVR Composition - All Barcodes');
      const badge=document.createElement('span');badge.className='number';badge.textContent=number;
      heading.replaceChildren(badge,document.createTextNode(text));
      let header=section.querySelector('.overview-panel-header');
      if(!header){header=document.createElement('div');header.className='overview-panel-header';section.prepend(header);}
      header.prepend(heading);
      let actions=header.querySelector('.overview-panel-actions');
      if(!actions){actions=document.createElement('div');actions.className='overview-panel-actions';header.appendChild(actions);}
      const switches=section.querySelector('.barcode-scale-controls');if(switches)actions.appendChild(switches);
      header.classList.toggle('has-view-controls',!!switches);
      const exports=section.querySelector('.graph-export-controls');if(exports)header.appendChild(exports);
      section.querySelectorAll('.histogram-heading').forEach(old=>{if(!old.children.length)old.remove();});
      for(const graph of section.querySelectorAll('.js-plotly-plot')){
        const heatmap=graph.data.find(trace=>trace.type==='heatmap');
        const height=number===1?720:number===4?Math.max(540,(heatmap?.y?.length||18)*22+130):380;
        Object.assign(graph.style,{width:'100%',maxWidth:'100%',height:height+'px',minHeight:height+'px'});
        if(graph.parentElement!==section&&!graph.closest('.read-composition-layout'))
          Object.assign(graph.parentElement.style,{width:'100%',minWidth:'0',maxWidth:'100%'});
        graph.reportHeatmapResize?.disconnect();graph.reportOverviewResize?.disconnect();
        let lastWidth=0;
        const fit=()=>{
          const width=Math.floor(graph.getBoundingClientRect().width);
          if(width<200||width===lastWidth)return;lastWidth=width;
          const updates={autosize:false,width,height};
          if(number===1)updates['margin.t']=88;
          if(number===4)Object.assign(updates,{'margin.l':75,'margin.r':95,'margin.t':35,'margin.b':85,
            'xaxis.tickangle':-45,'xaxis.tickfont.size':12,'yaxis.tickfont.size':12});
          Plotly.relayout(graph,updates);
        };
        graph.reportOverviewResize=new ResizeObserver(()=>requestAnimationFrame(fit));
        graph.reportOverviewResize.observe(graph);requestAnimationFrame(fit);
      }
    }
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
