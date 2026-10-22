/* Offline exports for existing and lazily rendered report figures. */
(() => {
  if (window.reportGraphExportInstalled === 'v14') return;
  window.reportGraphExportCleanup?.();
  window.reportGraphExportInstalled = 'v14';
  const attached = new WeakSet();
  const NS = 'http://www.w3.org/2000/svg';
  const save = (blob, filename) => {
    const url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),30000);
  };
  const figureTitle = graph => {
    const heading=graph.closest('section,article')?.querySelector('h3,h2')?.cloneNode(true);
    heading?.querySelectorAll('.number').forEach(badge=>badge.remove());
    const original=heading?.textContent.trim() || graph.getAttribute('aria-label') || 'Telomere analysis';
    const shortTitles={
      'Telomeric Reads by Barcode':'Telomeric Reads',
      'Telomere Length by Barcode':'Telomere Lengths',
      'Telomere Length Distribution':'Telomere Distribution',
      'Telomere and Read Length per Read':'Read and Telomere Lengths',
      'TVR Composition - All Barcodes':'TVR Composition',
      'TVR Composition - Available Barcodes':'TVR Composition (Available Barcodes)',
      'TVR Position Along Telomeres':'TVR Positions',
      'Median Telomere Length by Chromosome and Barcode':'Chromosome Telomere Lengths',
      'Chromosome Comparison':'Telomere Lengths by Chromosome',
      'Telomeric repeat density':'Repeat Density',
      'Repeat composition in telomere region':'Repeat Composition',
      'Telomere Completeness & Kaplan-Meier Estimate':'Telomere Completeness',
      'Read completeness':'Read Completeness',
      'Kaplan-Meier telomere length':'KM Telomere Estimate'
    };
    const title=shortTitles[original]||original;
    const detail=graph.closest('#read-detail');
    const barcode=detail ? detail.dataset.barcodeLabel || [...detail.querySelectorAll('.breadcrumbs a')]
      .find(link=>/^#\/barcode\/[^/]+$/.test(link.getAttribute('href')))?.textContent.trim()
      : graph.closest('.barcode-page')?.dataset.label;
    const read=detail ? detail.dataset.readLabel || detail.querySelector('.read-summary-identity h2')?.textContent.trim() : '';
    const context=[barcode,read].filter(Boolean).join(' · ');
    return title+(context ? ' — '+context : '');
  };
  const svgFromURL = url => {
    const payload=url.slice(url.indexOf(',')+1);
    const text=url.slice(0,url.indexOf(',')).includes(';base64') ? atob(payload) : decodeURIComponent(payload);
    const documentSVG=new DOMParser().parseFromString(text,'image/svg+xml');
    if (documentSVG.querySelector('parsererror')) throw Error('Could not create the SVG image.');
    return documentSVG.documentElement;
  };
  const snapshot = async graph => {
    if (graph.matches('svg.km-interval')) {
      const svg=graph.cloneNode(true), originals=[graph,...graph.querySelectorAll('*')];
      [svg,...svg.querySelectorAll('*')].forEach((element,index)=>{
        const computed=getComputedStyle(originals[index]);
        ['fill','stroke','stroke-width','font-family','font-size','font-weight','text-anchor'].forEach(key=>element.style.setProperty(key,computed.getPropertyValue(key)));
      });
      svg.setAttribute('width',graph.viewBox.baseVal.width||360);
      svg.setAttribute('height',graph.viewBox.baseVal.height||112);
      return svg;
    }
    if (!graph._fullLayout || !window.Plotly) throw Error('Wait for the graph to finish loading.');
    const figure=JSON.parse(JSON.stringify({data:graph.data,layout:graph.layout}));
    const layout=figure.layout;
    const tracks=graph.classList.contains('read-density-chart');
    const heatmap=figure.data.some(trace=>trace.type==='heatmap');
    let width=tracks?1100:900,height=tracks?650:heatmap?Math.max(420,Math.min(800,(figure.data[0].y?.length||6)*42+150)):560;
    layout.font={family:'Arial, Helvetica, sans-serif',size:12,color:'#222222'};
    layout.paper_bgcolor='white';layout.plot_bgcolor='white';layout.title={text:''};
    layout.margin={l:tracks?130:heatmap?180:80,r:tracks?240:heatmap?120:30,t:tracks?45:20,b:tracks?80:85,autoexpand:true};
    Object.entries(layout).forEach(([key,axis])=>{
      if(!/^[xy]axis\d*$/.test(key)||!axis)return;
      axis.tickfont={family:'Arial, Helvetica, sans-serif',size:11,color:'#222222'};
      axis.title=typeof axis.title==='string'?{text:axis.title}:axis.title||{};
      axis.title.font={family:'Arial, Helvetica, sans-serif',size:13,color:'#222222'};
      axis.title.standoff=12;
      if(axis.visible!==false && axis.showticklabels!==false) {
        axis.showline=!heatmap;axis.linecolor='#333333';axis.linewidth=1;
        axis.ticks=heatmap?'':'outside';axis.ticklen=4;axis.tickcolor='#333333';
        axis.showgrid=!heatmap && key.startsWith('y');axis.gridcolor='#e8e8e8';axis.gridwidth=1;
        axis.zeroline=false;axis.automargin=true;
      }
    });
    layout.legend=tracks?{...layout.legend,orientation:'v',x:1.02,y:1,xanchor:'left',yanchor:'top',font:{size:11},bgcolor:'rgba(255,255,255,0)'}:
      {...layout.legend,orientation:'h',x:.5,xanchor:'center',y:-.14,yanchor:'top',font:{size:11},bgcolor:'rgba(255,255,255,0)'};
    if(tracks && layout.legend2)layout.legend2={...layout.legend2,orientation:'v',x:1.02,xanchor:'left',y:.62,yanchor:'top',maxheight:.65,font:{size:11}};
    (layout.annotations||[]).forEach(annotation=>{annotation.font={...annotation.font,family:'Arial, Helvetica, sans-serif',size:12};});
    figure.data.forEach(trace=>{
      if(trace.line?.width>0)trace.line.width=Math.max(1.5,Math.min(2,trace.line.width));
      if(trace.colorbar)trace.colorbar={...trace.colorbar,tickfont:{size:11},title:{...(typeof trace.colorbar.title==='string'?{text:trace.colorbar.title}:trace.colorbar.title),font:{size:12}}};
    });
    // The read-composition legend lives beside Plotly in the interactive page.
    const composition=graph.closest('.read-composition-layout');
    if (composition && figure.data.some(trace=>trace.type==='pie')) {
      const legendRows=[...composition.querySelectorAll('.read-composition-legend li')];
      figure.data=figure.data.map(trace=>trace.type!=='pie' ? trace : {...trace,showlegend:true,textinfo:'none',domain:{x:[0,.48],y:[.1,.9]},
        labels:trace.labels.map((label,index)=>{
          const percentage=legendRows[index]?.querySelector('strong')?.textContent.trim();
          return label+(percentage ? ' — '+percentage : '');
        })});
      width=800;height=Math.max(360,legendRows.length*22+60);
      layout.showlegend=true;layout.margin={l:20,r:20,t:20,b:20};
      layout.legend={x:.55,y:.5,xanchor:'left',yanchor:'middle',orientation:'v',font:{size:12},bgcolor:'rgba(255,255,255,0)'};
      (layout.annotations||[]).forEach(annotation=>{
        if((annotation.xref||'paper')==='paper' && (annotation.yref||'paper')==='paper' && annotation.x===.5 && annotation.y===.5) {
          annotation.x=.24;annotation.y=.5;
          annotation.xanchor='center';annotation.yanchor='middle';annotation.align='center';
        }
      });
    }
    layout.width=width;layout.height=height;
    const target=document.createElement('div');
    target.style.cssText=`position:absolute;left:-20000px;top:0;width:${width}px;height:${height}px`;
    document.body.appendChild(target);
    let svg,overlay;
    try {
      await Plotly.newPlot(target,figure.data,layout,{staticPlot:true,displayModeBar:false});
      svg=svgFromURL(await Plotly.toImage(target,{format:'svg',width,height}));
      overlay=graph.reportExportOverlay?.(Math.max(3,2400/width),target._fullLayout);
    } finally {Plotly.purge(target);target.remove();}
    if (overlay) {
      const image=document.createElementNS(NS,'image');
      for(const key of ['x','y','width','height']) image.setAttribute(key,overlay[key]);
      image.setAttribute('href',overlay.href);
      image.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href',overlay.href);
      svg.appendChild(image);
    }
    return svg;
  };
  const exportGraph = async (graph,format) => {
    if(format==='html') {
      const bundle=[...document.scripts].find(script=>script.textContent.includes('plotly.js v'))?.textContent;
      if(!bundle||!graph.data)throw Error('Interactive export is unavailable for this figure.');
      const title=figureTitle(graph);
      const escape=value=>value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      if(graph.reportInteractiveRead&&window.renderReadTracks) {
        const payload=JSON.stringify(graph.reportInteractiveRead).replace(/</g,'\\u003c');
        const runtime='window.readMappingSummary='+window.readMappingSummary.toString()+';window.renderReadTracks='+window.renderReadTracks.toString()+';renderReadTracks(document.querySelector("main"),'+payload+');';
        const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{margin:20px;font-family:Arial;color:#14263c}h1{text-align:center;font-size:22px;margin:24px 0;font-weight:700}.read-density-panel>h3{display:none}.read-sequence-controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}button,input,select{padding:6px}.note{font-size:13px;color:#65788c}</style></head><body><h1>'+escape(title)+'</h1><main></main><script>'+bundle.replace(/<\/script/gi,'<\\/script')+'<\/script><script>'+runtime.replace(/<\/script/gi,'<\\/script')+'<\/script></body></html>';
        const filename=title.replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,160)||'plot';
        save(new Blob([html],{type:'text/html;charset=utf-8'}),filename+'.html');return;
      }
      const figure=JSON.parse(JSON.stringify({data:graph.data,layout:graph.layout}));
      const composition=graph.closest('.read-composition-layout');
      if(composition&&figure.data.some(trace=>trace.type==='pie')) {
        const rows=[...composition.querySelectorAll('.read-composition-legend li')];
        for(const trace of figure.data.filter(trace=>trace.type==='pie')) {
          trace.showlegend=true;trace.textinfo='none';trace.domain={x:[0,.48],y:[.1,.9]};
          trace.labels=trace.labels.map((label,index)=>{
            const percentage=rows[index]?.querySelector('strong')?.textContent.trim();
            return label+(percentage?' — '+percentage:'');
          });
        }
        figure.layout.showlegend=true;
        figure.layout.margin={l:20,r:20,t:90,b:20};
        figure.layout.legend={x:.55,y:.5,xanchor:'left',yanchor:'middle',orientation:'v',font:{size:14}};
        for(const annotation of figure.layout.annotations||[]) {
          if((annotation.xref||'paper')==='paper'&&(annotation.yref||'paper')==='paper'&&annotation.x===.5&&annotation.y===.5)
            Object.assign(annotation,{x:.24,y:.5,xanchor:'center',yanchor:'middle',align:'center'});
        }
      }
      delete figure.layout.width;delete figure.layout.height;figure.layout.autosize=true;
      figure.layout.margin={...figure.layout.margin,t:Math.max(90,figure.layout.margin?.t||0)};
      figure.layout.title={text:'<b>'+escape(title)+'</b>',x:.5,xanchor:'center',y:.97,yanchor:'top',pad:{t:18,b:16}};
      const payload=JSON.stringify(figure).replace(/</g,'\\u003c');
      const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{margin:0;font-family:Arial}#plot{width:100%;height:100vh;min-height:500px}</style></head><body><div id="plot"></div><script>'+bundle.replace(/<\/script/gi,'<\\/script')+'<\/script><script>const figure='+payload+';Plotly.newPlot("plot",figure.data,figure.layout,{responsive:true,displaylogo:false,scrollZoom:true});<\/script></body></html>';
      const filename=title.replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,160)||'plot';
      save(new Blob([html],{type:'text/html;charset=utf-8'}),filename+'.html');return;
    }
    const svg=await snapshot(graph);
    const width=Number(svg.getAttribute('width'))||svg.viewBox.baseVal.width;
    const height=Number(svg.getAttribute('height'))||svg.viewBox.baseVal.height;
    if (!(width>0 && height>0)) throw Error('Graph dimensions are unavailable.');
    const measure=document.createElement('canvas').getContext('2d');measure.font='600 14px Arial';
    const lines=[];let line='';
    for(const word of figureTitle(graph).split(/\s+/)) {
      const candidate=line?line+' '+word:word;
      if(line && measure.measureText(candidate).width>width-32){lines.push(line);line=word;}
      else line=candidate;
    }
    if(line)lines.push(line);
    const headingHeight=38+Math.max(0,lines.length-1)*18;
    const outer=document.createElementNS(NS,'svg');
    outer.setAttribute('xmlns',NS);outer.setAttribute('width',width);outer.setAttribute('height',height+headingHeight);
    outer.setAttribute('viewBox',`0 0 ${width} ${height+headingHeight}`);
    const background=document.createElementNS(NS,'rect');
    background.setAttribute('width','100%');background.setAttribute('height','100%');background.setAttribute('fill','white');outer.appendChild(background);
    const title=document.createElementNS(NS,'text');title.setAttribute('x',width/2);title.setAttribute('y',25);
    title.setAttribute('class','export-figure-title');title.setAttribute('text-anchor','middle');
    title.setAttribute('font-family','Arial, sans-serif');title.setAttribute('font-size',14);
    title.setAttribute('font-weight',700);title.setAttribute('fill','#222222');
    lines.forEach((line,index)=>{
      const span=document.createElementNS(NS,'tspan');span.setAttribute('x',width/2);span.setAttribute('dy',index?18:0);span.textContent=line;title.appendChild(span);
    });
    outer.appendChild(title);svg.setAttribute('y',headingHeight);outer.appendChild(svg);
    const serialized=new XMLSerializer().serializeToString(outer);
    const filename=figureTitle(graph)
      .replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,160)||'telomere-graph';
    if(format==='svg') {save(new Blob([serialized],{type:'image/svg+xml;charset=utf-8'}),filename+'.svg');return;}
    const factor=Math.max(3,2400/width);
    const canvas=document.createElement('canvas');canvas.width=Math.ceil(width*factor);canvas.height=Math.ceil((height+headingHeight)*factor);
    const image=new Image(),url=URL.createObjectURL(new Blob([serialized],{type:'image/svg+xml;charset=utf-8'}));
    try {
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('PNG conversion failed. Try SVG instead.'));image.src=url;});
      const context=canvas.getContext('2d');if(!context)throw Error('Image export is unavailable in this browser.');
      context.drawImage(image,0,0,canvas.width,canvas.height);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
      if(!blob)throw Error('PNG conversion failed. Try SVG instead.');save(blob,filename+'.png');
    } finally {URL.revokeObjectURL(url);}
  };
  window.reportExportGraph=exportGraph;
  const attach = graph => {
    if(attached.has(graph) || !graph.parentNode || !graph.closest('main')) return;
    attached.add(graph);
    const composition=graph.closest('.read-composition-layout');
    const previous=(composition||graph).previousElementSibling;
    if(previous?.classList.contains('graph-export-controls'))previous.remove();
    const toolbar=document.createElement('div');toolbar.className='graph-export-controls';
    toolbar.style.cssText='display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0;grid-column:1/-1';
    const status=document.createElement('span');status.setAttribute('role','status');status.style.fontSize='13px';
    const buttons=[];
    for(const [format,label] of [['png','Save PNG'],...(graph.data?[['html','Save interactive HTML']]:[])]) {
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.style.cssText='padding:7px 10px;border:1px solid #ccd8e8;border-radius:6px;background:white;color:#2456a6;cursor:pointer';
      button.onclick=async()=>{
        buttons.forEach(b=>b.disabled=true);status.textContent='Preparing image…';
        try{await exportGraph(graph,format);status.textContent='File saved.';}
        catch(error){status.textContent=error.message||'Image export failed.';}
        finally{buttons.forEach(b=>b.disabled=false);}
      };
      buttons.push(button);toolbar.appendChild(button);
    }
    toolbar.appendChild(status);
    if(composition) composition.before(toolbar);else graph.before(toolbar);
  };
  const scan = root => {
    if(root.nodeType!==1 && root!==document) return;
    if(root.matches?.('.js-plotly-plot,svg.km-interval')) attach(root);
    root.querySelectorAll('.js-plotly-plot,svg.km-interval').forEach(attach);
  };
  let observer;
  window.reportGraphExportCleanup=()=>{
    observer?.disconnect();
    document.querySelectorAll('.graph-export-controls').forEach(toolbar=>toolbar.remove());
  };
  const start = () => {
    document.querySelectorAll('.graph-export-controls').forEach(toolbar=>toolbar.remove());
    scan(document);
    observer=new MutationObserver(records=>records.forEach(record=>{
      if(record.type==='attributes')scan(record.target);
      else record.addedNodes.forEach(scan);
    }));
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
