window.reportBarcodeScaleUI=(section,graph)=>{
  section.querySelector('.barcode-scale-controls')?.remove();
  section.style.gridColumn='span 4';
  graph.style.minHeight='720px';graph.style.height='720px';
  graph.style.width='100%';graph.style.maxWidth='none';
  delete graph.layout.width;graph.layout.autosize=true;
  graph.reportBarcodeResizeObserver?.disconnect();
  const resize=()=>{if(graph.isConnected&&graph.offsetWidth>0)Plotly.Plots.resize(graph);};
  graph.reportBarcodeResizeObserver=new ResizeObserver(resize);
  graph.reportBarcodeResizeObserver.observe(graph);
  const sourceTraces=graph.data.filter(t=>['box','violin'].includes(t.type)||t.meta?.barcodeDistribution)
    .map(t=>{const copy=JSON.parse(JSON.stringify(t));delete copy.x;return copy;});
  const readLabels=new Map();
  for(const trace of sourceTraces){
    trace.customdata=(trace.customdata||[]).map(identity=>{
      const [barcodeId,readId,savedLabel]=identity;
      if(!readLabels.has(barcodeId)){
        let reads=window.reportReadRows?.(barcodeId);
        if(!reads){const saved=document.getElementById(barcodeId)?.querySelector('.read-data');reads=saved?JSON.parse(saved.textContent):[];}
        readLabels.set(barcodeId,new Map((reads||[]).map(read=>[read.id,read.label])));
      }
      return [barcodeId,readId,savedLabel||readLabels.get(barcodeId).get(readId)||'Read number unavailable'];
    });
    trace.hovertemplate='%{customdata[2]}<br>Telomere length: %{y:.3f} kb<br>Click to open read<extra>%{fullData.name}</extra>';
  }
  const names=sourceTraces.map(t=>t.name);
  if(graph.reportReadClickHandler)graph.removeListener('plotly_click',graph.reportReadClickHandler);
  graph.reportReadClickHandler=event=>{
    const point=event.points?.[0];
    if(!point||!['scatter','violin','box'].includes(point.data.type)||!Number.isInteger(point.pointNumber))return;
    const identity=point.customdata||point.data.customdata?.[point.pointNumber];
    if(!Array.isArray(identity)||!identity[0]||!identity[1]||!document.getElementById(identity[0]))return;
    location.hash='#/barcode/'+identity[0]+'/read/'+identity[1];
  };
  graph.on('plotly_click',graph.reportReadClickHandler);
  const heading=section.querySelector('h2');
  let header=heading?.closest('.histogram-heading');
  if(heading&&!header){header=document.createElement('div');header.className='histogram-heading';heading.before(header);header.appendChild(heading);}
  const controls=document.createElement('div');controls.className='histogram-controls barcode-scale-controls';
  controls.setAttribute('role','group');controls.setAttribute('aria-label','Telomere distribution view and scale');
  controls.style.cssText='display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0';
  const buttons=[];
  for(const [label,type] of [['Linear','linear'],['Logarithmic','log']]){
    const button=document.createElement('button');button.type='button';button.textContent=label;
    const update=()=>{for(const item of buttons){const active=item.type===(graph.layout.yaxis?.type||'linear');item.button.setAttribute('aria-pressed',String(active));item.button.style.background=active?'#2d65ce':'white';item.button.style.color=active?'white':'#20324c';}};
    button.style.cssText='font:600 15px Segoe UI,Arial,sans-serif;padding:10px 18px;border:1px solid #ccd8e8;border-radius:7px;cursor:pointer';
    button.onclick=()=>Plotly.relayout(graph,{'yaxis.type':type,'yaxis.autorange':true,'yaxis.rangemode':type==='log'?'normal':'tozero'}).then(update);
    buttons.push({button,type});controls.appendChild(button);
  }
  const viewButtons=[];
  for(const [label,type] of [['Scatter plot','scatter'],['Violin plot','violin']]){
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.style.cssText='font:600 15px Segoe UI,Arial,sans-serif;padding:10px 18px;border:1px solid #ccd8e8;border-radius:7px;cursor:pointer';
    if(type==='scatter')button.style.marginLeft='12px';
    button.onclick=async()=>{
      viewButtons.forEach(item=>item.button.disabled=true);
      try{
        const data=sourceTraces.map((trace,index)=>{
          const result={...trace,type};
          delete result.boxpoints;delete result.points;delete result.box;
          delete result.spanmode;delete result.span;delete result.bandwidth;delete result.scalemode;
          delete result.mode;delete result.jitter;delete result.pointpos;
          result.meta={...((typeof trace.meta==='object')?trace.meta:{}),barcodeDistribution:true};
          if(type==='violin')Object.assign(result,{points:'all',spanmode:'hard',scalemode:'width',box:{visible:false},pointpos:0});
          else {
            delete result.fillcolor;delete result.line;
            Object.assign(result,{mode:'markers',x:trace.y.map((_,i)=>index+(((i*2654435761>>>0)%1000)/999-.5)*.32),
              marker:{...trace.marker,size:5,opacity:.65}});
          }
          return result;
        });
        const layout=JSON.parse(JSON.stringify(graph.layout));
        layout.height=720;layout.updatemenus=[];layout.showlegend=false;
        delete layout.width;layout.autosize=true;
        layout.xaxis={...layout.xaxis,type:type==='scatter'?'linear':'category',
          tickmode:'array',tickvals:type==='scatter'?names.map((_,i)=>i):names,ticktext:names,
          categoryorder:'array',categoryarray:names,autorange:true,tickangle:-45};
        delete layout.xaxis.range;
        for(const a of layout.annotations||[])if(a.name==='group-statistics'){
          const index=typeof a.x==='number'?Math.round(a.x):names.indexOf(a.x);
          a.x=type==='scatter'?index:names[index];
        }
        await Plotly.react(graph,data,layout,{responsive:true,displaylogo:false});
        await Plotly.Plots.resize(graph);
      }finally{viewButtons.forEach(item=>item.button.disabled=false);refresh();}
    };
    viewButtons.push({button,type});controls.appendChild(button);
  }
  if(header)header.appendChild(controls);else graph.before(controls);
  const refresh=()=>{
    for(const {button,type} of [...buttons,...viewButtons]){
      const active=type===((type==='scatter'||type==='violin')?graph.data.find(t=>['box','violin','scatter'].includes(t.type))?.type:(graph.layout.yaxis?.type||'linear'));
      button.setAttribute('aria-pressed',String(active));button.style.background=active?'#2d65ce':'white';button.style.color=active?'white':'#20324c';
    }
  };
  refresh();graph.on?.('plotly_relayout',refresh);
  graph.layout.meta={...graph.layout.meta,barcodeLengthScale:true};
  Plotly.relayout(graph,{updatemenus:[],autosize:true,height:720,'margin.t':graph.layout.annotations?.some(a=>a.name==='group-statistics')?88:25,meta:graph.layout.meta}).then(()=>{
    const initial=graph.data.some(t=>t.type==='violin')?1:0;viewButtons[initial].button.click();
  });
};
(() => {
  const start=()=>{
    const section=[...document.querySelectorAll('#run-overview section')].find(s=>s.querySelector('h2')?.textContent.includes('Telomere Length by Barcode'));
    const graph=section?.querySelector('.js-plotly-plot');if(graph)window.reportBarcodeScaleUI(section,graph);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
