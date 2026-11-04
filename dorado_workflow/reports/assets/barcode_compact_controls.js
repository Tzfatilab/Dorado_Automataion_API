/* Compact barcode tools; retain the original controls and their event handlers. */
(() => {
  if(window.reportCompactBarcodeControls)return;
  window.reportCompactBarcodeControls=true;
  const style=document.createElement('style');
  style.textContent=`
    #run-overview>.barcode-names{display:none!important}
    .barcode-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px 20px;margin:8px 0 12px;font-size:13px}
    .barcode-page>.breadcrumbs>.barcode-toolbar{margin:0;gap:8px 24px;min-width:0;padding-left:12px}
    .barcode-page>.breadcrumbs>.barcode-toolbar label{white-space:nowrap}
    .barcode-toolbar .barcode-name-editor{display:flex;align-items:center;gap:12px!important;margin:0!important;font-size:13px}
    .barcode-toolbar .barcode-name-editor input{width:240px!important;max-width:100%;padding:5px 10px!important;height:30px;box-sizing:border-box;font:inherit}
    .barcode-toolbar .barcode-exclusion-banner{display:flex;align-items:center;gap:8px;margin:0!important;padding:0!important;border:0!important;background:none!important;font-size:13px}
    .barcode-toolbar .barcode-exclusion-banner label{gap:5px!important}
    .barcode-toolbar .barcode-exclusion-banner>span{display:none!important}
    .barcode-toolbar .barcode-exclusion-banner[data-excluded="true"]::after{content:'Excluded';color:#994b15;background:#fff0d9;border-radius:4px;padding:2px 6px;font-size:12px}
    .barcode-toolbar .barcode-names{margin:0!important;padding:0!important;border:0!important;font-size:12px}
    .barcode-toolbar .barcode-names summary{cursor:pointer;color:#52647b}
    .barcode-toolbar .barcode-names[open]{flex-basis:100%;padding:8px!important;background:#f7f9fc}
    .barcode-toolbar .barcode-names button,.barcode-toolbar .barcode-names input{font-size:12px;margin:5px;padding:4px 7px}
    .barcode-exclusion-controls{margin:10px 0!important;padding:10px 12px!important;font-size:13px}
    .barcode-exclusion-controls summary{cursor:pointer;font-weight:600}
    .barcode-exclusion-controls p{font-size:12px;margin:8px 0}
    .barcode-exclusion-controls button{padding:5px 8px!important;font-size:12px}
    .barcode-page>.breadcrumbs{gap:12px 20px}
    .barcode-page>.breadcrumbs>.barcode-toolbar{gap:10px 22px;padding:0 0 0 16px;border:0;border-left:1px solid #dce4ed;border-radius:0;background:transparent}
    .barcode-toolbar .barcode-name-editor{flex-direction:row;align-items:center!important;gap:10px!important;font-size:13px;font-weight:400;color:#42546b}
    .barcode-toolbar .barcode-name-editor input{height:32px;font-size:13px;font-weight:400;color:#14263c}
    .barcode-toolbar .barcode-exclusion-banner{display:flex;gap:8px;align-items:center}
    .barcode-toolbar .barcode-control-title{display:none}
    .barcode-toolbar .barcode-exclusion-banner label{min-height:32px;font-size:13px}
  `;
  document.head.appendChild(style);
  const parked=document.createDocumentFragment();let names=null,pending=false;
  // Function: compact.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Moves the existing barcode controls into the compact toolbar.
  const compact=()=>{
    pending=false;
    if(!names)names=document.querySelector('.barcode-names');
    if(names&&!names.dataset.compactTools){
      names.dataset.compactTools='true';names.open=false;
      names.querySelector('summary').textContent='Name tools';
      names.querySelectorAll('table,.table-export-controls,p:not([role="status"])').forEach(el=>el.hidden=true);
    }
    for(const page of document.querySelectorAll('.barcode-page')){
      const editor=page.querySelector('.barcode-name-editor'),banner=page.querySelector('.barcode-exclusion-banner');
      if(!editor&&!banner)continue;
      let toolbar=page.querySelector('.barcode-toolbar');
      if(!toolbar){toolbar=document.createElement('div');toolbar.className='barcode-toolbar';}
      const breadcrumbs=page.querySelector('.breadcrumbs');
      if(breadcrumbs&&toolbar.parentElement!==breadcrumbs)breadcrumbs.insertBefore(toolbar,breadcrumbs.querySelector('.barcode-step-navigation'));
      if(editor){
        if(!editor.dataset.compact){
          editor.dataset.compact='true';
          for(const node of editor.childNodes)if(node.nodeType===3)node.textContent='Rename barcode ';
          const input=editor.querySelector('input');if(input){input.placeholder='e.g. Control sample';input.title='Enter a display name, then press Enter or click outside the field to save.';}
        }
        if(editor.parentElement!==toolbar)toolbar.appendChild(editor);
      }
      if(banner){
        const label=banner.querySelector('label span');if(label&&label.textContent!=='Include in overview')label.textContent='Include in overview';
        const checkbox=banner.querySelector('input');if(checkbox)checkbox.title='Include this barcode in overview graphs and pooled statistics';
        if(banner.parentElement!==toolbar)toolbar.appendChild(banner);
      }
    }
    const controls=document.querySelector('.barcode-exclusion-controls');
    if(controls&&!controls.dataset.compact){controls.dataset.compact='true';controls.open=false;}
    if(names&&names.parentNode!==parked)parked.appendChild(names);
  };
  // Function: schedule.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Schedules one layout update on the next animation frame.
  const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(compact);}};
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    compact();
    new MutationObserver(records=>{
      if(records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches?.('.barcode-name-editor,.barcode-exclusion-banner,.barcode-names,.barcode-exclusion-controls')||n.querySelector?.('.barcode-name-editor,.barcode-exclusion-banner,.barcode-names,.barcode-exclusion-controls')))))schedule();
    }).observe(document.body,{childList:true,subtree:true});
    window.addEventListener('hashchange',schedule);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
