// Violin markers do not support per-point color arrays. Their explicit
// selection styling colors points without splitting/recomputing the density.
window.reportBarcodeShortColors=(figure,cutoffForTrace=trace=>{
  const id=trace.customdata?.[0]?.[0];
  return window.reportShortCutoff?.cutoffFor(id)??Number(document.getElementById(id)?.dataset.shortCutoffBp);
})=>{
  for(const trace of figure.data){
    if(!['box','violin'].includes(trace.type)&&!trace.meta?.barcodeDistribution)continue;
    const cutoff=cutoffForTrace(trace);
    trace.selectedpoints=(trace.y||[]).flatMap((value,index)=>
      typeof value==='number'&&Number.isFinite(value)&&value>=0&&Number.isFinite(cutoff)&&cutoff>0&&value<cutoff/1000?[index]:[]);
    trace.selected={marker:{color:'#ef4444',opacity:1}};
    trace.unselected={marker:{color:'#ffffff',opacity:1}};
  }
  return figure;
};

// Hollow read points with an explicit median and interquartile interval.
// Only presentation changes: observations and read-link identities stay intact.
window.reportBarcodeDistributionStyle=figure=>{
  const groups=figure.data.filter(t=>['box','violin'].includes(t.type)||t.meta?.barcodeDistribution);
  const layout=figure.layout;
  layout.shapes=(layout.shapes||[]).filter(s=>!String(s.name||'').startsWith('barcode-distribution-summary:'));
  if(!groups.length)return figure;
  const quantile=(values,p)=>{const index=(values.length-1)*p,low=Math.floor(index);return values[low]+(index-low)*((values[low+1]??values[low])-values[low]);};
  groups.forEach((trace,index)=>{
    Object.assign(trace,{type:'violin',points:'all',pointpos:0,jitter:.8,width:.85,
      fillcolor:'rgba(0,0,0,0)',line:{color:'rgba(0,0,0,0)',width:0},
      box:{visible:false},meanline:{visible:false},opacity:1,
      marker:{color:'#ffffff',size:7,opacity:1,line:{color:'#299b37',width:1}}});
    const values=(trace.y||[]).filter(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0).slice().sort((a,b)=>a-b);
    if(values.length<2)return;
    const q1=quantile(values,.25),median=quantile(values,.5),q3=quantile(values,.75);
    const id=trace.customdata?.[0]?.[0]||trace.name;
    const segment=(part,x0,x1,y0,y1)=>layout.shapes.push({
      name:'barcode-distribution-summary:'+id+':'+part,type:'line',xref:'x',yref:'y',
      x0,x1,y0,y1,line:{color:'#111111',width:3},layer:'above'});
    segment('iqr',index,index,q1,q3);
    segment('q1',index-.16,index+.16,q1,q1);
    segment('q3',index-.16,index+.16,q3,q3);
    segment('median',index-.3,index+.3,median,median);
  });
  layout.xaxis={...layout.xaxis,showgrid:false,showline:true,linecolor:'#111111',linewidth:2,
    ticks:'outside',tickcolor:'#111111',tickwidth:2,zeroline:false};
  layout.yaxis={...layout.yaxis,showgrid:true,gridcolor:'#777777',griddash:'dot',gridwidth:1,
    showline:true,linecolor:'#111111',linewidth:2,ticks:'outside',tickcolor:'#111111',tickwidth:2,zeroline:false};
  return window.reportBarcodeShortColors(figure);
};

// Function: window.reportBarcodeScaleUI.
// Inputs: section (containing report section); graph (Plotly graph element)
// Outputs: Attaches scale/view controls to the existing length chart.
window.reportBarcodeScaleUI=(section,graph)=>{
  section.querySelector('.barcode-scale-controls')?.remove();
  section.style.gridColumn='span 4';
  graph.style.minHeight='720px';graph.style.height='720px';
  graph.style.width='100%';graph.style.maxWidth='none';
  delete graph.layout.width;graph.layout.autosize=true;
  graph.reportBarcodeResizeObserver?.disconnect();
  // Function: resize.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Resizes the visible Plotly chart to its container.
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
  // Function: graph.reportReadClickHandler.
  // Inputs: event (browser pointer/event object)
  // Outputs: Handles navigation from a plotted read using its stable identity.
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
  controls.setAttribute('role','group');controls.setAttribute('aria-label','Telomere distribution scale');
  controls.style.cssText='display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0';
  const buttons=[];
  for(const [label,type] of [['Linear','linear'],['Logarithmic','log']]){
    const button=document.createElement('button');button.type='button';button.textContent=label;
    // Function: update.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Synchronizes scale-button appearance with the current chart axis.
    const update=()=>{for(const item of buttons){const active=item.type===(graph.layout.yaxis?.type||'linear');item.button.setAttribute('aria-pressed',String(active));item.button.style.background=active?'#2d65ce':'white';item.button.style.color=active?'white':'#20324c';}};
    button.style.cssText='font:600 15px Segoe UI,Arial,sans-serif;padding:10px 18px;border:1px solid #ccd8e8;border-radius:7px;cursor:pointer';
    // Function: button.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    button.onclick=()=>Plotly.relayout(graph,{'yaxis.type':type,'yaxis.autorange':true,'yaxis.rangemode':type==='log'?'normal':'tozero'}).then(update);
    buttons.push({button,type});controls.appendChild(button);
  }
  const bandwidthNote=document.createElement('span');
  bandwidthNote.textContent='Red fill: below cutoff · Black bars: median and IQR';bandwidthNote.title='Red-filled circles: telomere length below the selected short cutoff. Other reads: hollow green circles. Black bars: median and 25th–75th percentiles. Point spread uses a shared 1 kb bandwidth.';bandwidthNote.style.cssText='font-size:13px;color:#52647a;margin-left:8px';
  controls.appendChild(bandwidthNote);
  // Function: applyViolin.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Promise completing after the length-distribution chart is redrawn.
  const applyViolin=async()=>{
    const data=sourceTraces.map(trace=>{
      const result={...trace,type:'violin'};
      delete result.boxpoints;delete result.mode;delete result.span;
      delete result.bandwidth;delete result.jitter;
      // Degenerate groups have no estimable density; Plotly renders their points.
      const bandwidth=new Set(trace.y).size>1?1:0;
      Object.assign(result,{points:'all',bandwidth,spanmode:'hard',scalemode:'width',box:{visible:false},pointpos:0});
      result.meta={...((typeof trace.meta==='object')?trace.meta:{}),barcodeDistribution:true};
      return result;
    });
    const layout=JSON.parse(JSON.stringify(graph.layout));
    layout.height=720;layout.updatemenus=[];layout.showlegend=false;
    delete layout.width;layout.autosize=true;
    layout.xaxis={...layout.xaxis,type:'category',tickmode:'array',tickvals:names,ticktext:names,
      categoryorder:'array',categoryarray:names,autorange:false,
      range:[-.5,Math.max(.5,names.length-.5)],tickangle:-45};
    for(const a of layout.annotations||[])if(a.name==='group-statistics'){
      const index=typeof a.x==='number'?Math.round(a.x):names.indexOf(a.x);
      a.x=names[index];
    }
    window.reportBarcodeDistributionStyle({data,layout});
    await Plotly.react(graph,data,layout,{responsive:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d']});
    await Plotly.Plots.resize(graph);
    refresh();
  };
  if(header)header.appendChild(controls);else graph.before(controls);
  // Function: refresh.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Updates visible chart controls for the current report state.
  const refresh=(event)=>{
    // Autoscale/double-click should restore every selected barcode slot,
    // including empty groups; manual range zoom remains available.
    if(event?.['xaxis.autorange']===true){
      const count=graph.layout.xaxis?.categoryarray?.length||0;
      Plotly.relayout(graph,{'xaxis.autorange':false,'xaxis.range':[-.5,Math.max(.5,count-.5)]});
    }
    for(const {button,type} of buttons){
      const active=type===(graph.layout.yaxis?.type||'linear');
      button.setAttribute('aria-pressed',String(active));button.style.background=active?'#2d65ce':'white';button.style.color=active?'white':'#20324c';
    }
  };
  refresh();graph.on?.('plotly_relayout',refresh);
  graph.layout.meta={...graph.layout.meta,barcodeLengthScale:true};
  Plotly.relayout(graph,{updatemenus:[],autosize:true,height:720,'margin.t':graph.layout.annotations?.some(a=>a.name==='group-statistics')?88:25,meta:graph.layout.meta}).then(()=>{
    return applyViolin();
  });
};
(() => {
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    const section=[...document.querySelectorAll('#run-overview section')].find(s=>s.querySelector('h2')?.textContent.includes('Telomere Length by Barcode'));
    const graph=section?.querySelector('.js-plotly-plot');if(graph)window.reportBarcodeScaleUI(section,graph);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
