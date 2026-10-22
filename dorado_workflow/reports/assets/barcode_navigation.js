/* Offline navigation follows the same order as the overview barcode links. */
(() => {
  const start=()=>{
    const pages=[...document.querySelectorAll('.barcode-page')];
    pages.forEach((page,index)=>{
      const breadcrumbs=page.querySelector('.breadcrumbs');
      if(!breadcrumbs||breadcrumbs.querySelector('.barcode-step-navigation'))return;
      const nav=document.createElement('span');nav.className='barcode-step-navigation';
      nav.style.cssText='display:flex;gap:8px;margin-left:auto;flex-wrap:wrap';
      for(const [label,target] of [['Previous barcode',pages[index-1]],['Next barcode',pages[index+1]]]){
        const button=document.createElement('button');button.type='button';button.textContent=label;
        button.disabled=!target;
        button.style.cssText='padding:7px 12px;border:1px solid #ccd8e8;border-radius:6px;background:white;color:#2456a6;cursor:pointer';
        if(target){button.title=target.dataset.label;button.onclick=()=>{location.hash='#/barcode/'+target.id;window.scrollTo(0,0);};}
        else{button.style.opacity='.45';button.style.cursor='default';}
        nav.appendChild(button);
      }
      breadcrumbs.appendChild(nav);
    });
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
