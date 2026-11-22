/* A presentation cutoff over recorded lengths; never changes read membership. */
(() => {
  const start=()=>{
    if(window.reportShortCutoff)return;
    const pages=[...document.querySelectorAll('.barcode-page')];
    let facts=[];try{facts=JSON.parse(document.getElementById('barcode-exclusion-data')?.textContent||'[]');}catch{}
    const valid=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
    const positive=n=>valid(n)&&n>0;
    const key='telomere-short-cutoff-v1:'+location.pathname+':'+pages.map(p=>p.id).join(',');
    let override=null;try{const saved=JSON.parse(localStorage.getItem(key));if(positive(saved))override=saved;}catch{}
    const factFor=page=>facts.find(f=>f.id===(typeof page==='string'?page:page?.id));
    const cutoffFor=page=>{
      if(override!==null)return override;
      if(page)return factFor(page)?.cutoff??(Number(page?.dataset.originalShortCutoffBp)||null);
      const values=[...new Set(facts.map(f=>f.cutoff))];return values.length===1?values[0]:null;
    };
    // Keep sorted lengths once, making repeated cutoff changes inexpensive.
    const sorted=new WeakMap();
    const percentage=(stats,cutoff)=>{
      if(!stats||stats.requested===false||!Array.isArray(stats.lengths)||!positive(cutoff))return null;
      if(!sorted.has(stats))sorted.set(stats,stats.lengths.filter(valid).slice().sort((a,b)=>a-b));
      const values=sorted.get(stats);if(!values.length)return null;
      let lo=0,hi=values.length;while(lo<hi){const mid=(lo+hi)>>1;if(values[mid]<cutoff)lo=mid+1;else hi=mid;}
      return 100*lo/values.length;
    };
    for(const page of pages)page.dataset.originalShortCutoffBp=page.dataset.shortCutoffBp||'';
    const groupValues=(data,x)=>{
      const group=data.find(t=>['box','violin'].includes(t.type)&&t.name===x);
      if(group)return (group.y||[]).filter(valid);
      const dots=data.find(t=>t.meta==='read-links'&&t.name==='Individual reads');
      return dots?(dots.y||[]).filter((v,i)=>valid(v)&&Math.round(dots.x[i])===Number(x)):null;
    };
    const groupCutoff=(data,x,page)=>{
      if(page)return cutoffFor(page);
      const trace=data.find(t=>['box','violin'].includes(t.type)&&t.name===x);
      const id=trace?.customdata?.[0]?.[0];
      return override??factFor(id)?.cutoff??null;
    };
    const transform=(figure,page=null,kind=null)=>{
      const layout=figure.layout||(figure.layout={}),data=figure.data||[];
      if(!page)window.reportBarcodeShortColors?.(figure,trace=>groupCutoff(data,trace.name,page));
      const cutoff=cutoffFor(page),kb=cutoff/1000;
      const groups=(layout.annotations||[]).some(a=>a.name==='group-statistics-labels'&&/Short/.test(a.text));
      if((kind||groups)&&positive(cutoff)&&!(layout.shapes||[]).some(s=>s.name==='short-telomere-cutoff')){
        const horizontal=kind!=='histogram';
        layout.shapes=[...(layout.shapes||[]),{name:'short-telomere-cutoff',type:'line',
          xref:horizontal?'paper':'x',yref:horizontal?'y':'paper',
          x0:horizontal?0:cutoff,x1:horizontal?1:cutoff,y0:horizontal?kb:0,y1:horizontal?kb:1,
          line:{color:'#b45309',width:1.5,dash:'dash'}}];
        layout.annotations=[...(layout.annotations||[]),{name:'short-telomere-cutoff-label',showarrow:false,
          text:'Short telomeres: < '+kb+' kb',xref:horizontal?'paper':'x',yref:horizontal?'y':'paper',
          x:horizontal?1:cutoff,y:horizontal?kb:1,xanchor:horizontal?'right':'left',yanchor:'bottom',font:{size:12,color:'#92400e'}}];
      }
      if(!positive(cutoff)&&!page){
        layout.shapes=(layout.shapes||[]).filter(s=>s.name!=='short-telomere-cutoff'||s.xref==='x');
        layout.annotations=(layout.annotations||[]).filter(a=>a.name!=='short-telomere-cutoff-label');
      }
      if(!positive(cutoff)&&page){
        layout.shapes=(layout.shapes||[]).filter(s=>s.name!=='short-telomere-cutoff');
        layout.annotations=(layout.annotations||[]).filter(a=>a.name!=='short-telomere-cutoff-label');
      }
      for(const shape of layout.shapes||[]){
        if(shape.name!=='short-telomere-cutoff')continue;
        if(shape.xref==='x'&&shape.yref==='paper'){
          if(positive(cutoff))shape.x0=shape.x1=cutoff;
        }else{
          let value=cutoff;
          if(!page&&shape.xref==='x'){
            const groups=data.filter(t=>['box','violin'].includes(t.type));
            value=groupCutoff(data,groups[Math.round((shape.x0+shape.x1)/2)]?.name,null);
          }
          if(positive(value))shape.y0=shape.y1=value/1000;
        }
      }
      for(const annotation of layout.annotations||[]){
        if(annotation.name==='short-telomere-cutoff-label'&&positive(cutoff)){
          annotation.text='Short telomeres: < '+kb+' kb';
          if(annotation.xref==='x')annotation.x=cutoff;else annotation.y=kb;
        }
        if(annotation.name==='group-statistics'){
          const lines=String(annotation.text).split('<br>'),values=groupValues(data,annotation.x);
          const threshold=groupCutoff(data,annotation.x,page);
          // Only panels with a Short row participate; mean-only panels stay intact.
          if(values&&lines.length>=3&&layout.annotations.some(a=>a.name==='group-statistics-labels'&&/Short/.test(a.text))){
            lines[lines.length-1]=positive(threshold)&&values.length?(100*values.filter(v=>v<threshold/1000).length/values.length).toFixed(1):'Unavailable';
            annotation.text=lines.join('<br>');
          }
        }
        if(annotation.name==='group-statistics-labels'&&/Short/.test(annotation.text)){
          const thresholds=page?[cutoff]:data.filter(t=>['box','violin'].includes(t.type)).map(t=>groupCutoff(data,t.name,null));
          const unique=[...new Set(thresholds)];
          annotation.text=annotation.text.replace(/Short[^<]*(?:&lt;[^<]*)?%/,unique.length===1&&positive(unique[0])?'Short (&lt; '+unique[0]/1000+' kb), %':'Short, %');
        }
      }
      return figure;
    };
    const toolbar=document.createElement('form');toolbar.className='short-cutoff-controls';
    toolbar.innerHTML='<label>Short telomere cutoff (kb) <input type="number" min="0.001" step="any" required aria-label="Short telomere cutoff (kb)"></label><button type="submit">Apply</button><button type="button" class="short-cutoff-reset">Reset to run settings</button><span role="status"></span>';
    document.querySelector('main')?.prepend(toolbar);
    const input=toolbar.querySelector('input'),status=toolbar.querySelector('[role="status"]');
    const defaults=[...new Set(facts.map(f=>f.cutoff).filter(positive))];
    const sync=()=>{
      input.value=override!==null?override/1000:defaults.length===1?defaults[0]/1000:'';
      input.placeholder=defaults.length>1?'Per-barcode settings':'Enter cutoff';
      status.textContent=override!==null?'Telomere length < '+override/1000+' kb · Applied to all barcodes.':'Using recorded run settings.';
    };
    const updateCards=()=>{
      for(const page of pages){
        const cutoff=cutoffFor(page),fact=factFor(page);
        page.dataset.shortCutoffBp=positive(cutoff)?cutoff:'';
        for(const card of page.querySelectorAll('.km-card.short-card')){
          const method=page.dataset.mismatchEnabled==='true'?'mismatch':'exact';
          const pct=percentage(fact?.measurements?.[method]?.after,cutoff);
          card.querySelector('strong').textContent=pct===null?'\u2014':pct.toFixed(1)+'%';
          card.querySelector('span:not(.short-icon)').innerHTML='<b>Short telomeres</b><br>'+ (positive(cutoff)?'&lt; '+cutoff+' bp':'Cutoff unavailable');
        }
        const route=document.querySelector('#run-overview .barcode-statistics-table a[href="#/barcode/'+page.id+'"]');
        const row=route?.closest('tr');
        for(const root of [page,row].filter(Boolean)){
          for(const cell of root.querySelectorAll('[data-short-method]')){
            const stats=fact?.measurements?.[cell.dataset.shortMethod]?.after,pct=percentage(stats,cutoff);
            const value=cell.querySelector('strong');if(!value)continue;
            value.textContent=stats?.requested===false?'Off':pct===null?'—':pct.toFixed(root===page?1:2)+'%';
            const note=stats?.requested===false?'This matching mode was not requested.':pct===null?'Measured telomere lengths unavailable.':'Telomere length < '+cutoff/1000+' kb; '+stats.lengths.length+' measured after-filtering reads.';
            cell.title=note;cell.querySelector('.short-method-note')?.replaceChildren(document.createTextNode(note));
            if(pct!==null){value.removeAttribute('aria-label');value.removeAttribute('title');}
          }
          for(const note of root.querySelectorAll('.short-card-note,.short-summary-note'))note.textContent='After filtering · '+(positive(cutoff)?'Telomere length < '+cutoff/1000+' kb':'Cutoff unavailable');
        }
      }
    };
    const attached=new WeakSet(),pending=new Map();
    const updateGraph=graph=>{
      if(pending.has(graph))return pending.get(graph);
      if(!graph.layout||!graph.data)return Promise.resolve();
      if(!(graph.layout.shapes||[]).some(s=>s.name==='short-telomere-cutoff')&&!(graph.layout.annotations||[]).some(a=>a.name==='group-statistics-labels'&&/Short/.test(a.text)))return Promise.resolve();
      const copy=transform({data:graph.data.map(trace=>({...trace})),layout:JSON.parse(JSON.stringify(graph.layout))},graph.closest('.barcode-page'),graph.closest('[data-length-population-chart]')?.dataset.lengthPopulationChart);
      const patch={};for(const field of ['shapes','annotations'])if(JSON.stringify(copy.layout[field])!==JSON.stringify(graph.layout[field]))patch[field]=copy.layout[field];
      const colored=copy.data.map((trace,index)=>Array.isArray(trace.selectedpoints)&&
        JSON.stringify(trace.selectedpoints)!==JSON.stringify(graph.data[index].selectedpoints)?index:-1).filter(index=>index>=0);
      if(!Object.keys(patch).length&&!colored.length)return Promise.resolve();
      const task=Promise.resolve().then(()=>colored.length?Plotly.update(graph,{
        selectedpoints:colored.map(index=>copy.data[index].selectedpoints),
        'selected.marker.color':'#ef4444','selected.marker.opacity':1,
        'unselected.marker.color':'#ffffff','unselected.marker.opacity':1
      },patch,colored):Plotly.relayout(graph,patch)).finally(()=>pending.delete(graph));
      pending.set(graph,task);return task;
    };
    const scan=()=>Promise.all([...document.querySelectorAll('.js-plotly-plot')].map(graph=>{
      if(!attached.has(graph)&&graph.on){attached.add(graph);graph.on('plotly_afterplot',()=>{updateGraph(graph).catch(()=>{});});}
      return updateGraph(graph);
    }));
    // Two frames let the busy state paint before table calculations occupy the browser.
    const painted=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const submit=toolbar.querySelector('[type=submit]');
    let activeUpdate=null;
    const busy=value=>{
      toolbar.setAttribute('aria-busy',String(value));
      toolbar.querySelectorAll('input,button').forEach(control=>control.disabled=value);
      submit.textContent=value?'Updating...':'Apply';
      if(value)status.textContent='Updating short telomere statistics and graphs...';
    };
    const apply=value=>{
      if(value!==null&&!positive(value))return Promise.reject(new Error('Short telomere cutoff must be a finite positive number of base pairs.'));
      if(activeUpdate)return activeUpdate;
      busy(true);
      activeUpdate=(async()=>{
        try{
          await painted();
          override=value;try{if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,JSON.stringify(value));}catch{}
          updateCards();
          const work=[];
          document.dispatchEvent(new CustomEvent('short-cutoff-change',{detail:{waitUntil:promise=>work.push(Promise.resolve(promise))}}));
          // Include renders queued by read-table population/filter listeners, too.
          for(const graph of document.querySelectorAll('.saved-histogram'))if(graph.populationRender)work.push(graph.populationRender);
          await Promise.all([...work,scan()]);
          await scan();
          await painted();
          sync();
        }catch(error){
          status.textContent='The update could not finish. Press Apply to retry.';
          throw error;
        }finally{
          busy(false);activeUpdate=null;
        }
      })();
      return activeUpdate;
    };
    toolbar.onsubmit=event=>{
      event.preventDefault();
      // Shift decimal units directly: 2.007 kb must be exactly 2007 bp,
      // rather than a floating-point product slightly above the strict cutoff.
      const [significand,exponent='0']=input.value.toLowerCase().split('e');
      const value=Number(significand+'e'+(Number(exponent)+3));
      input.setCustomValidity(positive(value)?'':'Enter a finite positive cutoff.');
      if(toolbar.reportValidity())apply(value).catch(()=>{});
    };
    input.oninput=()=>input.setCustomValidity('');
    toolbar.querySelector('.short-cutoff-reset').onclick=()=>apply(null).catch(()=>{});
    window.reportShortCutoff={cutoffFor,percentage,transform,set:apply,get value(){return override;},get updating(){return activeUpdate!==null;}};
    sync();updateCards();scan().catch(()=>{});
    let queued=false;
    new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(()=>{queued=false;scan().catch(()=>{});});}}).observe(document.querySelector('main'),{childList:true,subtree:true});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
