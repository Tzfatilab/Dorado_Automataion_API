"""Offline read browser over the exported post-filtered population.

Search hits are not base coverage or TVR blocks, so those unsupported columns
remain unavailable until the scientific outputs supply their definitions.
"""
import json
from collections import Counter
from .motif_colors import motif_color


def read_rows(barcode, include_unfiltered=False):
    """Join exported length records to reads without changing their population."""
    population = barcode.metrics.get('filtered_length_records')
    available = population and population.status == 'available'
    if not available and not include_unfiltered:
        return None
    records = list(population.value) if available else []
    retained = {record['read_id'] for record in records}
    if include_unfiltered:
        records.extend(dict(read_id=read.id, original_id=read.original_id, length_bp=None)
                       for read in barcode.reads if read.id not in retained)
    reads = {read.id: read for read in barcode.reads}
    rows = []
    for record in records:
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
        # Show exported motif evidence even when an older coverage file cannot
        # support percentages for the expanded interval. Counts are not coverage.
        motif_counts = None
        track = read.tracks.get('motifs') if read else None
        interval = read.calls.get('tvr_inclusive', {}).get('interval') if read else None
        if (track and interval and track.status == 'available' and interval.status == 'available'
                and 'tvr_inclusive' in track.value['methods']):
            counts = Counter(hit['motif'] for hit in track.value['matches']
                if hit['method'] == 'tvr_inclusive' and hit['role'] == 'tvr'
                and hit['end'] > interval.value['start'] and hit['start'] < interval.value['end'])
            motif_counts = [dict(motif=motif, count=count, color=motif_color(motif))
                            for motif, count in sorted(counts.items())]
        regions = read.tracks.get('tvr_regions') if read else None
        def call_length(method):
            fact = read.calls.get(method, {}).get('reported_length') if read else None
            return fact.value if fact and fact.status == 'available' else None
        rows.append(dict(source_note=('Saved NanoTel read details. This read is outside the displayed filtered population and is excluded from filtered summary statistics.' if include_unfiltered and record['read_id'] not in retained else None), motifs=motif_counts, exact_length=call_length('exact'), tvr_length=call_length('tvr_inclusive'), regions=regions.value if regions and regions.status == 'available' else None, canonical=measurement('canonical_pct'), tvr=measurement('tvr_pct'),
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
    # Serial numbers belong to the source read, including reads excluded from
    # the table's population. Never substitute plot rank for the original number.
    table_ids = {row['id'] for row in rows or []}
    extra_rows = [row for row in read_rows(barcode, include_unfiltered=True) if row['id'] not in table_ids]
    extra_payload = json.dumps(extra_rows, ensure_ascii=True).replace('<', '\\u003c')
    labels = {}
    for read in barcode.reads:
        serial = read.metrics.get('read_number')
        if serial and serial.status == 'available':
            labels[read.original_id] = f'Read {int(serial.value)}'
    label_payload = json.dumps(labels, ensure_ascii=True).replace('<', '\\u003c')

    return '''<section class="read-browser"><div class="reads-toolbar">
<h2><span class="number">8</span>Reads <small class="read-total"></small></h2>
<div class="read-controls"><label>Search <input class="read-search" type="search" placeholder="Search reads..."></label>
<label>Chromosome <select class="read-chromosome"><option value="">All chromosomes</option></select></label>
<label>Arm <select class="read-arm"><option value="">All arms</option></select></label>
<label>Sort by <select class="read-sort"><option value="original">Original order</option><option value="length">Total read length</option><option value="telomere">Filtered telomere length</option><option value="tvr_length">Telomere including TVRs</option><option value="tvr">TVR %</option><option value="canonical">Canonical %</option><option value="blocks">TVR blocks</option><option value="label">Read number</option><option value="chromosomes">Chromosome</option><option value="arms">Arm</option></select></label>
<label>Order <select class="read-sort-direction" disabled><option value="desc">Highest first</option><option value="asc">Lowest first</option></select></label>
<label>Show <select class="read-limit"><option>10</option><option>25</option><option>50</option><option>100</option></select></label>
</div></div><p class="note">Post-filtered telomeric reads. Canonical/TVR percentages use unique matched bases within the TVR-inclusive telomere interval. Categories may overlap; they need not sum to 100%. TVR blocks merge adjacent or overlapping TVR hits. Missing exports remain unavailable.</p>
<div class="reads-scroll"><table class="reads-table"><thead><tr><th>Read number</th><th>Filtered telomere (kb)</th><th>Including TVRs (kb)</th><th>Total read length (kb)</th><th>Canonical %</th><th>TVR %</th><th># TVR blocks</th><th>Chromosome</th><th>Arm</th></tr></thead><tbody></tbody></table></div>
<p class="read-status" role="status"></p><nav class="read-pagination" aria-label="Read pages"></nav>
<script type="application/json" class="read-data">''' + payload + '</script><script type="application/json" class="read-labels">' + label_payload + '</script><script type="application/json" class="read-details">' + extra_payload + '</script></section>'


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
    // Saved plots may include reads removed by final filtering. Keep these
    // detail-only records out of the filtered read table and its statistics.
    const labelData = section.querySelector('.read-labels');
    const savedLabels = labelData ? JSON.parse(labelData.textContent) : {};
    const shortLabels = new Map();
    Object.entries(savedLabels).forEach(([header,label]) => {
      const key = header.split(/\s+/)[0];
      shortLabels.set(key, shortLabels.has(key) && shortLabels.get(key) !== label ? null : label);
    });
    const extraData = section.querySelector('.read-details');
    const detailRows = [...(rows || []), ...(extraData ? JSON.parse(extraData.textContent) : [])];
    const censoredHeaders = new Set();
    const knownHeaders = new Set(detailRows.flatMap(r => [r.header, r.header.split(/\s+/)[0]]));
    page.querySelectorAll('.histogram-figure').forEach(script => {
      let figure; try { figure = JSON.parse(script.textContent); } catch (_) { return; }
      (figure.data || []).forEach(trace => {
        // Censoring is a source status, not the same as exclusion by a filter.
        // Use NanoTel's explicitly exported censored-read trace; do not infer
        // completeness from lengths or absence from this trace.
        if (trace.name === 'Censored reads (observed lengths)' && Array.isArray(trace.text)) {
          trace.text.forEach(header => censoredHeaders.add(header));
        }
        (Array.isArray(trace.text) ? trace.text : []).forEach(text => {
          const match = /^Read: (.*?)<br>/.exec(text);
          if (!match || knownHeaders.has(match[1])) return;
          knownHeaders.add(match[1]);
          const value = pattern => { const found = pattern.exec(text); return found ? Number(found[1].replaceAll(',', '')) : null; };
          detailRows.push({id:'saved-'+encodeURIComponent(match[1]),header:match[1],label:savedLabels[match[1]] || shortLabels.get(match[1]) || 'Read '+match[1],
            length:value(/Read length: ([\d,]+) bp/),exact_length:value(/Telomere length \(exact\): ([\d,]+) bp/),
            plot_only:true,telomere:null,tvr_length:null,canonical:null,tvr:null,blocks:null,overlap:null,unassigned:null,
            chromosomes:[],arms:[],motifs:null,regions:null,
            source_note:'Saved pre-final-filter plot record. '+(/Edge filter: Removed/.test(text)?'Removed by the edge filter. ':'')+'Only measurements exported in this plot are available here.'});
        });
      });
    });
    detailRows.forEach(read => {
      read.censored = censoredHeaders.has(read.header) || censoredHeaders.has(read.header.split(/\s+/)[0]);
    });
    browsers.set(page.id, {page, rows:detailRows});
    section.querySelector('.read-total').textContent = rows ? `(${rows.length.toLocaleString()} telomeric reads)` : '';
    if (rows === null) {
      section.querySelector('.read-status').textContent = 'Post-filtered read records were not exported.';
      section.querySelectorAll('input,select').forEach(el => el.disabled = true); return;
    }
    const search = section.querySelector('.read-search');
    const chromosome = section.querySelector('.read-chromosome');
    const arm = section.querySelector('.read-arm');
    const limit = section.querySelector('.read-limit');
    const sort = section.querySelector('.read-sort');
    const direction = section.querySelector('.read-sort-direction');
    const originalOrder = new Map(rows.map((r,index) => [r,index]));
    [[chromosome,'chromosomes'], [arm,'arms']].forEach(([select,key]) => {
      [...new Set(rows.flatMap(r => r[key]))].sort((a,b) => a.localeCompare(b,undefined,{numeric:true})).forEach(value => {
        const option = node('option',value,select); option.value = value;
      });
    });
    let current = 1;
    function render() {
      const filtered = rows.filter(r => (r.label + ' ' + r.header).toLowerCase().includes(search.value.toLowerCase()) &&
        (!chromosome.value || r.chromosomes.includes(chromosome.value)) && (!arm.value || r.arms.includes(arm.value)));
      direction.disabled = sort.value === 'original';
      if (sort.value !== 'original') {
        const key = sort.value, sign = direction.value === 'asc' ? 1 : -1;
        // Sort the filtered copy, never the source population or plotted records.
        // Missing values stay last in either direction; equal values keep source order.
        const value = read => Array.isArray(read[key]) ? read[key].join(', ') || null : read[key];
        filtered.sort((a,b) => {
          const av=value(a), bv=value(b);
          if (av == null || bv == null) return av == null && bv == null ? originalOrder.get(a)-originalOrder.get(b) : av == null ? 1 : -1;
          const comparison = typeof av === 'number' && typeof bv === 'number' ? av-bv : String(av).localeCompare(String(bv),undefined,{numeric:true});
          return sign*comparison || originalOrder.get(a)-originalOrder.get(b);
        });
      }
      const size = Number(limit.value), count = Math.max(1,Math.ceil(filtered.length/size));
      current = Math.min(current,count);
      const body = section.querySelector('tbody'); body.replaceChildren();
      filtered.slice((current-1)*size,current*size).forEach(r => {
        const tr = node('tr','',body), td = node('td','',tr);
        const href = '#/barcode/' + page.id + '/read/' + r.id;
        if (r.id) { const a = node('a',r.label,td); a.href = href; a.title = r.header; }
        else node('span',r.label,td);
        [kb(r.telomere),kb(r.tvr_length),kb(r.length),pct(r.canonical),pct(r.tvr),formatCount(r.blocks),r.chromosomes.join(', ') || 'Unavailable',r.arms.join(', ') || 'Unavailable'].forEach(text => node('td',text,tr));

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
    [search,chromosome,arm,limit,sort,direction].forEach(el=>el.addEventListener(el===search?'input':'change',()=>{current=1;render();}));
    render();
  });
  window.reportReadRows = id => browsers.get(id)?.rows || [];
  // One reusable detail shell avoids generating thousands of hidden pages.
  window.showReadDetail = hash => {
    detail.hidden=true;
    const match = /^#\\/barcode\\/([^/]+)\\/read\\/([^/]+)$/.exec(hash);
    if(!match)return false;
    const source=browsers.get(match[1]);
    let read=source && source.rows.find(r=>r.id===match[2]);
    // Preserve bookmarked fallback routes created by older reports.
    if(!read && source && match[2].startsWith('saved-')) {
      try { const header=decodeURIComponent(match[2].slice(6));read=source.rows.find(r=>r.header===header || r.header.split(/\s+/)[0]===header); } catch (_) {}
    }
    if(!read)return false;
    detail.replaceChildren(); detail.hidden=false;
    const nav=node('nav','',detail); nav.className='breadcrumbs';
    node('a','All Barcodes',nav).href='#/'; node('span','\u203a',nav);
    node('a',source.page.dataset.label,nav).href='#/barcode/'+match[1]; node('span','\u203a '+read.label,nav);
    const back=node('a','Back to '+source.page.dataset.label,detail);
    back.href='#/barcode/'+match[1]; back.className='barcode-link read-back';
    node('h2',read.label.startsWith('Read ')?read.label:'Read: '+read.label,detail);
    if(read.source_note) node('p',read.source_note,detail).className='note';
    if(read.censored) {
      const status=node('div','',detail);status.className='read-censor-notice';status.setAttribute('role','note');
      node('strong','Censored read (incomplete telomere)',status);
      node('p','NanoTel marked this read as censored. Its observed telomere length is a lower bound: the full telomere may be longer. Censoring does not mean the read failed filtering. These observations are accounted for in the Kaplan-Meier estimate.',status);
    }
    const list=node('dl','',detail);
    [['Filtered telomere length (kb)',kb(read.telomere)],['Exact telomere length (kb)',kb(read.exact_length)],['Telomere including TVRs (kb)',kb(read.tvr_length)],['Total read length (kb)',kb(read.length)],['Chromosome',read.chromosomes.join(', ')||'Unavailable'],['Arm',read.arms.join(', ')||'Unavailable'],['Canonical %',pct(read.canonical)],['TVR %',pct(read.tvr)],['TVR blocks',formatCount(read.blocks)],['Bases matching both categories',formatCount(read.overlap)],['Unassigned bases',formatCount(read.unassigned)]].forEach(([key,value])=>{node('dt',key,list);node('dd',value,list);});
    node('p',read.plot_only ? 'Lengths shown here come from the saved pre-final-filter plot. This read is not added to the filtered table or summary statistics.' : 'Lengths use exported post-filtered telomere records and source read lengths. Repeat percentages use the source-exported TVR-inclusive interval, which may differ from the filtered telomere length above. Overlapping categories are reported explicitly. Unavailable values are not inferred.',detail).className='note';
    node('h3','TVR motifs in the TVR-inclusive telomere',detail);
    if (read.motifs == null) {
      node('p','Motif exports are unavailable for this interval.',detail);
    } else if (!read.motifs.length) {
      node('p','No exported TVR matches in this interval.',detail);
    } else {
      const table=node('table','',detail);table.className='reads-table';
      const head=node('tr','',node('thead','',table));
      ['TVR sequence','Exported matches'].forEach(text=>node('th',text,head));
      const body=node('tbody','',table);
      read.motifs.forEach(item=>{
        const row=node('tr','',body),cell=node('td','',row);
        const swatch=node('span','\u25cf ',cell);swatch.style.color=item.color;
        node('span',item.motif,cell);node('td',formatCount(item.count),row);
      });
      node('p','Each exported match overlapping the TVR-inclusive boundary counts once, including boundary-crossing matches. Match counts retain overlaps and are not base percentages or TVR block counts. Canonical repeats are excluded.',detail).className='note';
    }
    if (read.tvr == null && !read.plot_only) {
      node('p','TVR base coverage is unavailable for the TVR-inclusive interval. Older coverage exports may need regeneration; unavailable does not mean zero TVRs.',detail).className='note';
    }
    if (read.regions !== null && read.regions !== undefined) {
      node('h3','TVR blocks in the TVR-inclusive telomere interval',detail);
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
