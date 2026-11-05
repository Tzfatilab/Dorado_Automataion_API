/* Barcode navigation styled to match the approved toolbar reference. */
(() => {
  if(window.reportBarcodeHeaderDesign)return;
  window.reportBarcodeHeaderDesign=true;
  // Function: icon.
  // Inputs: paths (SVG path markup)
  // Outputs: CSS URL containing a self-contained SVG icon.
  const icon=paths=>'url("data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+paths+'</svg>')+'")';
  const grid=icon('<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M8 3v18M15 3v18M3 8h18M3 15h18"/>');
  const dna=icon('<path d="M5 2c0 9 14 11 14 20M19 2C19 11 5 13 5 22M6 5h12M9 9h6M9 15h6M6 19h12"/>');
  const pen=icon('<path d="m4 16-1 5 5-1L21 7a2 2 0 0 0-4-4L4 16ZM14 6l4 4M4 16l4 4"/>');
  const style=document.createElement('style');style.id='barcode-header-reference-design';
  style.textContent=`
    .barcode-page>.breadcrumbs.barcode-header{display:flex;align-items:center;flex-wrap:wrap;gap:14px 18px;margin:16px 0!important;padding:16px 18px!important;border:1px solid #d7e2f3;border-radius:20px;background:linear-gradient(115deg,#f8faff,#f3f7fd);box-shadow:0 2px 5px #183a6b08;font-family:inherit;color:#122650;box-sizing:border-box}
    .barcode-header>a:first-child{position:relative;display:inline-flex;align-items:center;gap:9px;flex-shrink:0;padding:10px 14px!important;border:1px solid #bdcfe9!important;border-radius:13px!important;background:white!important;box-shadow:0 2px 3px #183a6b0a;color:#18346b!important;font-size:14px;line-height:20px;white-space:nowrap;margin-right:14px}
    .barcode-header>a:first-child::before{content:'';width:20px;height:20px;background:currentColor;mask:${grid} center/contain no-repeat;-webkit-mask:${grid} center/contain no-repeat}
    .barcode-header>a:first-child::after{content:'\u203a';position:absolute;right:-25px;top:8px;font-size:26px;font-weight:400;color:#18346b}
    .barcode-header>.barcode-identity{display:inline-flex;align-items:center;gap:9px;padding:10px 14px;border-radius:13px;background:#deebff;color:#112651;white-space:nowrap;font-size:0;line-height:20px}
    .barcode-header>.barcode-identity::before{content:'';width:24px;height:24px;flex-shrink:0;background:#2454a4;mask:${dna} center/contain no-repeat;-webkit-mask:${dna} center/contain no-repeat}
    .barcode-header>.barcode-identity::after{content:attr(data-current-label);font-size:16px;font-weight:700;line-height:20px}
    .barcode-page>.breadcrumbs.barcode-header>.barcode-toolbar{display:flex!important;align-items:center!important;flex-wrap:wrap;gap:12px 20px!important;margin:0!important;padding:0 0 0 20px!important;border:0!important;border-left:1px solid #c8d7ee!important;border-radius:0!important;background:transparent!important;min-width:0;flex:1}
    .barcode-header .barcode-toolbar .barcode-name-editor{display:flex!important;flex-direction:row!important;align-items:center!important;gap:12px!important;margin:0!important;font-size:14px!important;font-weight:400!important;color:#18305e;white-space:nowrap}
    .barcode-header .barcode-name-editor::before{content:'';display:block;width:21px;height:21px;flex-shrink:0;background:#294b83;mask:${pen} center/contain no-repeat;-webkit-mask:${pen} center/contain no-repeat}
    .barcode-header .barcode-toolbar .barcode-name-editor input{width:clamp(180px,14vw,250px)!important;max-width:100%;height:42px!important;padding:9px 13px!important;border:1px solid #bdcfe9!important;border-radius:13px!important;background:white!important;box-shadow:0 2px 3px #183a6b08!important;font:400 14px/20px 'Segoe UI',Arial,sans-serif!important;color:#172c51;box-sizing:border-box}
    .barcode-header .barcode-name-editor input::placeholder{color:#737b88;opacity:1}
    .barcode-header .barcode-toolbar .barcode-exclusion-banner{display:flex!important;align-items:center;gap:8px!important;margin:0!important;padding:0 0 0 20px!important;border:0!important;border-left:1px solid #c8d7ee!important;background:none!important}
    .barcode-header .barcode-exclusion-banner .barcode-control-title,.barcode-header .barcode-exclusion-banner>span{display:none!important}
    .barcode-header .barcode-exclusion-banner label{display:inline-flex!important;align-items:center!important;gap:10px!important;min-height:42px;padding:8px 13px;border-radius:13px;background:#e9eef6;color:#53647c;cursor:pointer;box-sizing:border-box;white-space:nowrap}
    .barcode-header .barcode-exclusion-banner label:has(input:checked){background:#d8e7ff;color:#112651}
    .barcode-header .barcode-exclusion-banner label span{font-size:0!important}
    .barcode-header .barcode-exclusion-banner label span::after{content:'Include in summary'!important;font-size:14px!important;font-weight:700;line-height:20px}
    .barcode-header .barcode-exclusion-banner input[type=checkbox]{appearance:none;-webkit-appearance:none;position:relative;width:23px;height:23px;flex-shrink:0;margin:0;border:1px solid #a9b9d0;border-radius:5px;background:white;cursor:pointer}
    .barcode-header .barcode-exclusion-banner input[type=checkbox]:checked{background:#1154e8;border-color:#1154e8;box-shadow:0 1px 2px #154ec526}
    .barcode-header .barcode-exclusion-banner input[type=checkbox]:checked::after{content:'';position:absolute;left:7px;top:3px;width:6px;height:11px;border:solid white;border-width:0 2px 2px 0;transform:rotate(45deg)}
    .barcode-header .barcode-step-navigation{display:flex!important;align-items:center;flex-wrap:nowrap;gap:8px!important;margin-left:auto!important;flex-shrink:0}
    .barcode-header .barcode-step-navigation button{display:inline-flex;align-items:center;justify-content:center;gap:9px;min-height:42px;padding:9px 14px!important;border:1px solid #bdcfe9!important;border-radius:13px!important;background:white!important;box-shadow:0 2px 3px #183a6b0a;color:#18346b!important;font:400 14px/20px 'Segoe UI',Arial,sans-serif!important;cursor:pointer;white-space:nowrap}
    .barcode-header .barcode-step-navigation button:first-child::before{content:'\u2190';font-size:23px;line-height:18px}
    .barcode-header .barcode-step-navigation button:last-child{background:linear-gradient(120deg,#173b70,#102d57)!important;border-color:#173b70!important;color:white!important;font-weight:600!important}
    .barcode-header .barcode-step-navigation button:last-child::after{content:'\u2192';font-size:23px;line-height:18px}
    .barcode-header button:disabled{opacity:.45!important;cursor:default!important}
    .barcode-header input:focus-visible,.barcode-header button:focus-visible,.barcode-header a:focus-visible{outline:2px solid #2365d9;outline-offset:3px}
    .barcode-header button:not(:disabled):hover,.barcode-header>a:first-child:hover{filter:brightness(.97)}
    .barcode-summary-actions{display:flex;align-items:center;flex-wrap:nowrap;gap:16px;margin-left:auto;max-width:100%;overflow-x:auto}
    .barcode-summary-actions>.barcode-exclusion-banner{flex-shrink:0}
    @media(max-width:1100px){.barcode-page>.breadcrumbs.barcode-header{gap:12px;padding:12px!important}.barcode-page>.breadcrumbs.barcode-header>.barcode-toolbar{padding-left:14px!important;gap:12px!important}.barcode-header .barcode-toolbar .barcode-exclusion-banner{padding-left:14px!important}.barcode-header .barcode-name-editor input{width:180px!important}}
    @media(max-width:650px){.barcode-page>.breadcrumbs.barcode-header>.barcode-toolbar{flex-basis:100%;border-left:0!important;padding-left:0!important}.barcode-header .barcode-toolbar .barcode-name-editor{flex-wrap:wrap;white-space:normal}.barcode-header .barcode-toolbar .barcode-exclusion-banner{border-left:0!important;padding-left:0!important}.barcode-summary-actions{width:100%;gap:8px}.barcode-header .barcode-step-navigation{margin-left:auto!important}.barcode-header .barcode-step-navigation button{padding:8px!important;gap:5px;font-size:12px!important}.barcode-header .barcode-exclusion-banner label{padding:8px 10px;gap:7px!important}.barcode-header .barcode-exclusion-banner label span::after{font-size:12px!important}}
  `;
  document.head.appendChild(style);
  // Function: decorate.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Applies the barcode-toolbar presentation to existing controls.
  const decorate=()=>{
    for(const page of document.querySelectorAll('.barcode-page')){
      const header=page.querySelector('.breadcrumbs');if(!header)continue;
      header.classList.add('barcode-header');
      const identity=[...header.children].find(el=>el.tagName==='SPAN'&&!el.classList.contains('barcode-step-navigation'));
      if(identity){identity.classList.add('barcode-identity');const text=identity.textContent.replace(/^[\s\u203a\u00bb>]+/,'');if(identity.dataset.currentLabel!==text)identity.dataset.currentLabel=text;}
      const toolbar=page.querySelector('.barcode-toolbar');if(toolbar&&toolbar.parentElement!==header)header.insertBefore(toolbar,header.querySelector('.barcode-step-navigation'));
      // Keep inclusion and navigation together when the name field wraps.
      const banner=page.querySelector('.barcode-exclusion-banner');
      const navigation=header.querySelector('.barcode-step-navigation');
      if(toolbar&&banner&&navigation){
        let actions=toolbar.querySelector('.barcode-summary-actions');
        if(!actions){actions=document.createElement('div');actions.className='barcode-summary-actions';toolbar.appendChild(actions);}
        if(banner.parentElement!==actions)actions.appendChild(banner);
        if(navigation.parentElement!==actions)actions.appendChild(navigation);
      }
      const check=page.querySelector('.barcode-exclusion-banner input');if(check)check.title='Include this barcode in overview graphs and pooled statistics';
    }
  };
  // Function: schedule.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Schedules one layout update on the next animation frame.
  let pending=false;const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;decorate();});}};
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    decorate();
    new MutationObserver(records=>{
      if(records.some(r=>r.target.parentElement?.matches('.barcode-identity')||r.target.matches?.('.barcode-identity')||[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches?.('.barcode-toolbar,.barcode-name-editor,.barcode-exclusion-banner,.breadcrumbs')||n.querySelector?.('.barcode-toolbar,.barcode-exclusion-banner')))))schedule();
    }).observe(document.body,{childList:true,subtree:true,characterData:true});
    window.addEventListener('hashchange',schedule);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
