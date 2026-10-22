/* Keep chromosome captions close to the x-axis without changing the data. */
(() => {
  if(window.reportChromosomeSpacingInstalled)return;
  window.reportChromosomeSpacingInstalled=true;
  const attached=new WeakSet();
  const fix=plot=>{
    if(!plot.layout||plot.layout.xaxis?.title?.text!=='Chromosome'||!plot.closest('.barcode-page'))return;
    const section=plot.closest('section');
    plot.style.minHeight='0';plot.style.marginBottom='0';
    const note=section?.querySelector('p.note:last-child');
    if(note)note.style.marginTop='4px';
    const bottom=plot._fullLayout?.margin?.b??plot.layout.margin?.b??65;
    if(bottom>60)Plotly.relayout(plot,{'margin.b':55,height:Math.max(300,(plot.layout.height||350)-(bottom-55))});
  };
  const scan=()=>document.querySelectorAll('.barcode-page .js-plotly-plot').forEach(plot=>{
    fix(plot);
    if(!attached.has(plot)&&plot.on){attached.add(plot);plot.on('plotly_afterplot',()=>fix(plot));}
  });
  const start=()=>{scan();new MutationObserver(scan).observe(document.querySelector('main'),{childList:true,subtree:true});};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
