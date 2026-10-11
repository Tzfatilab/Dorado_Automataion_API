"""Offline read browser over the exported post-filtered population.

Search hits are not base coverage or TVR blocks, so those unsupported columns
remain unavailable until the scientific outputs supply their definitions.
"""
import json


def read_rows(barcode):
    """Join exported length records to reads without changing their population."""
    population = barcode.metrics.get('filtered_length_records')
    if not population or population.status != 'available':
        return None
    reads = {read.id: read for read in barcode.reads}
    rows = []
    for record in population.value:
        read = reads.get(record.get('read_id'))
        length = read.metrics.get('read_length') if read else None
        serial = read.metrics.get('read_number') if read else None
        # Use saved numbers, never a page index that changes with filtering.
        label = (f'Read {int(serial.value)}' if serial and serial.status == 'available'
                 else record['original_id'].split()[0])
        chromosomes, arms = set(), set()
        if read and read.alignments.status == 'available':
            # Retain multiple source assignments; never invent a chromosome arm.
            for alignment in read.alignments.value:
                for key, target in [('chromosome', chromosomes), ('arm', arms)]:
                    fact = alignment.get(key)
                    if fact and fact.status == 'available':
                        target.add(str(fact.value))
        def measurement(key):
            fact = read.metrics.get(key) if read else None
            return fact.value if fact and fact.status == 'available' else None
        regions = read.tracks.get('tvr_regions') if read else None
        rows.append(dict(regions=regions.value if regions and regions.status == 'available' else None, canonical=measurement('canonical_pct'), tvr=measurement('tvr_pct'),
                         blocks=measurement('tvr_block_count'), overlap=measurement('repeat_overlap_bp'),
                         unassigned=measurement('repeat_unassigned_bp'), id=read.id if read else None,
                         header=read.original_id if read else record['original_id'],
                         label=label,
                         telomere=record['length_bp'],
                         length=length.value if length and length.status == 'available' else None,
                         chromosomes=sorted(chromosomes), arms=sorted(arms)))
    return rows


def reads_section(barcode):
    """Embed JSON safely; the browser inserts all source text with textContent."""
    rows = read_rows(barcode)
    payload = json.dumps(rows, ensure_ascii=True).replace('<', '\\u003c')
    return '''<section class="read-browser"><div class="reads-toolbar">
<h2><span class="number">7</span>Reads <small class="read-total"></small></h2>
<label>Search <input class="read-search" type="search" placeholder="Search reads..."></label>
<label>Chromosome <select class="read-chromosome"><option value="">All chromosomes</option></select></label>
<label>Arm <select class="read-arm"><option value="">All arms</option></select></label>
<label>Show <select class="read-limit"><option>10</option><option>25</option><option>50</option><option>100</option></select></label>
</div><p class="note">Post-filtered telomeric reads. Canonical/TVR percentages use unique matched bases within the exact telomere interval. Categories may overlap; they need not sum to 100%. TVR blocks merge adjacent or overlapping TVR hits. Missing exports remain unavailable.</p>
<div class="reads-scroll"><table class="reads-table"><thead><tr><th>Read number</th><th>Telomere length (kb)</th><th>Total read length (kb)</th><th>Canonical %</th><th>TVR %</th><th># TVR blocks</th><th>Chromosome</th><th>Arm</th><th></th></tr></thead><tbody></tbody></table></div>
<p class="read-status" role="status"></p><nav class="read-pagination" aria-label="Read pages"></nav>
<script type="application/json" class="read-data">''' + payload + '</script></section>'


READ_SCRIPT = """<script>
(() => {
  const detail = document.createElement('section');
  detail.id = 'read-detail'; detail.hidden = true;
  document.querySelector('main').appendChild(detail);
  const browsers = new Map();
  function node(tag, text, parent) {
    const el = document.createElement(tag); el.textContent = text;
    if (parent) parent.appendChild(el); return el;
  }
  function kb(value) { return value == null ? 'Unavailable' : (value / 1000).toLocaleString(undefined, {maximumFractionDigits:3}); }
  function pct(value) { return value == null ? 'Unavailable' : value.toFixed(1) + '%'; }
  function formatCount(value) { return value == null ? 'Unavailable' : value.toLocaleString(); }
  document.querySelectorAll('.read-browser').forEach(section => {
    const page = section.closest('.barcode-page');
    const rows = JSON.parse(section.querySelector('.read-data').textContent);
    browsers.set(page.id, {page, rows:rows || []});
    section.querySelector('.read-total').textContent = rows ? `(${rows.length.toLocaleString()} telomeric reads)` : '';
    if (rows === null) {
      section.querySelector('.read-status').textContent = 'Post-filtered read records were not exported.';
      section.querySelectorAll('input,select').forEach(el => el.disabled = true); return;
    }
    const search = section.querySelector('.read-search');
    const chromosome = section.querySelector('.read-chromosome');
    const arm = section.querySelector('.read-arm');
    const limit = section.querySelector('.read-limit');
    [[chromosome,'chromosomes'], [arm,'arms']].forEach(([select,key]) => {
      [...new Set(rows.flatMap(r => r[key]))].sort((a,b) => a.localeCompare(b,undefined,{numeric:true})).forEach(value => {
        const option = node('option',value,select); option.value = value;
      });
    });
    let current = 1;
    function render() {
      const filtered = rows.filter(r => (r.label + ' ' + r.header).toLowerCase().includes(search.value.toLowerCase()) &&
        (!chromosome.value || r.chromosomes.includes(chromosome.value)) && (!arm.value || r.arms.includes(arm.value)));
      const size = Number(limit.value), count = Math.max(1,Math.ceil(filtered.length/size));
      current = Math.min(current,count);
      const body = section.querySelector('tbody'); body.replaceChildren();
      filtered.slice((current-1)*size,current*size).forEach(r => {
        const tr = node('tr','',body), td = node('td','',tr);
        const href = '#/barcode/' + page.id + '/read/' + r.id;
        if (r.id) { const a = node('a',r.label,td); a.href = href; a.title = r.header; }
        else node('span',r.label,td);
        [kb(r.telomere),kb(r.length),pct(r.canonical),pct(r.tvr),formatCount(r.blocks),r.chromosomes.join(', ') || 'Unavailable',r.arms.join(', ') || 'Unavailable'].forEach(text => node('td',text,tr));
        const last = node('td','',tr);
        if (r.id) { const a = node('a','\u203a',last); a.href = href; a.setAttribute('aria-label','Open read '+r.label); }
      });
      section.querySelector('.read-status').textContent = filtered.length ? `${(current-1)*size+1}\u2013${Math.min(current*size,filtered.length)} of ${filtered.length.toLocaleString()} reads` : 'No reads match these filters.';
      const nav = section.querySelector('.read-pagination'); nav.replaceChildren();
      function button(text,target,disabled) {
        const b = node('button',text,nav); b.type='button'; b.disabled=disabled;
        if(target===current) b.setAttribute('aria-current','page');
        b.addEventListener('click',()=>{current=target;render();});
      }
      button('Previous',current-1,current===1);
      // Keep pagination bounded even for millions of reads.
      const numbers = [...new Set([1,current-1,current,current+1,count])].filter(n=>n>=1&&n<=count).sort((a,b)=>a-b);
      numbers.forEach((n,i)=>{if(i&&n>numbers[i-1]+1)node('span','...',nav);button(String(n),n,false);});
      button('Next',current+1,current===count);
    }
    [search,chromosome,arm,limit].forEach(el=>el.addEventListener(el===search?'input':'change',()=>{current=1;render();}));
    render();
  });
  // One reusable detail shell avoids generating thousands of hidden pages.
  window.showReadDetail = hash => {
    detail.hidden=true;
    const match = /^#\\/barcode\\/([^/]+)\\/read\\/([^/]+)$/.exec(hash);
    if(!match)return false;
    const source=browsers.get(match[1]), read=source && source.rows.find(r=>r.id===match[2]);
    if(!read)return false;
    detail.replaceChildren(); detail.hidden=false;
    const nav=node('nav','',detail); nav.className='breadcrumbs';
    node('a','All Barcodes',nav).href='#/'; node('span','\u203a',nav);
    node('a',source.page.dataset.label,nav).href='#/barcode/'+match[1]; node('span','\u203a '+read.label,nav);
    const back=node('a','Back to '+source.page.dataset.label,detail);
    back.href='#/barcode/'+match[1]; back.className='barcode-link read-back';
    node('h2',read.label.startsWith('Read ')?read.label:'Read: '+read.label,detail);
    const list=node('dl','',detail);
    [['Telomere length (kb)',kb(read.telomere)],['Total read length (kb)',kb(read.length)],['Chromosome',read.chromosomes.join(', ')||'Unavailable'],['Arm',read.arms.join(', ')||'Unavailable'],['Canonical %',pct(read.canonical)],['TVR %',pct(read.tvr)],['TVR blocks',formatCount(read.blocks)],['Bases matching both categories',formatCount(read.overlap)],['Unassigned bases',formatCount(read.unassigned)]].forEach(([key,value])=>{node('dt',key,list);node('dd',value,list);});
    node('p','Lengths use exported post-filtered telomere records and source read lengths. Repeat percentages use the source-exported exact interval, which may differ from the filtered telomere length above. Overlapping categories are reported explicitly. Unavailable values are not inferred.',detail).className='note';
    if (read.regions !== null && read.regions !== undefined) {
      node('h3','TVR blocks in the exact telomere interval',detail);
      const table=node('table','',detail); table.className='reads-table';
      const head=node('tr','',node('thead','',table));
      ['Start (bp)','End (bp)','Length (bp)'].forEach(label=>node('th',label,head));
      const body=node('tbody','',table);
      read.regions.forEach(block=>{
        const row=node('tr','',body);
        [block.start+1,block.end,block.end-block.start].forEach(value=>node('td',String(value),row));
      });
      node('p','Positions are 1-based inclusive on the analyzed read. Adjacent or overlapping TVR hits form one block; a block may contain multiple motifs.',detail).className='note';
    }
    const full=node('details','',detail);node('summary','Full source read header',full);node('p',read.header,full);
    document.querySelector('header h1').textContent='Telomere Analysis Summary - '+(read.label.startsWith('Read ')?read.label:'Read '+read.label);
    return true;
  };
})();
</script>"""
