"""Import versioned R coverage measurements; never calculate coverage here."""
import json
import math
import re
from .models import Availability as A, Evidence, Fact, unavailable

DEFINITION = 'union_coverage_tvr_interval_v2'
KEYS = ('canonical_pct', 'tvr_pct', 'tvr_block_count', 'repeat_overlap_bp', 'repeat_unassigned_bp')


def import_coverage(importer, barcode):
    """Validate source identity, denominator, coverage consistency and block bounds."""
    index = {}
    for read in barcode.reads:
        index.setdefault(read.original_id, []).append(read)
        for key in KEYS:
            read.metrics[key] = unavailable('Versioned NanoTel coverage export not available')
    seen = set()
    for path in importer.files('*read*_coverage.json'):
        if path.parent.name != 'report_details' or not (path.name.startswith(barcode.label+'_read') or
                (re.fullmatch(r'read\d+_coverage.json', path.name) and path.parent.parent.name.lower() == barcode.label.lower())):
            continue
        targets = []
        try:
            row = json.loads(path.read_text(encoding='utf-8-sig'))
            targets = index.get(row.get('read_id'), [])
            if len(targets) != 1:
                raise ValueError('unmatched or ambiguous read identity')
            read = targets[0]
            if read.id in seen:
                raise ValueError('duplicate coverage exports')
            seen.add(read.id)
            ev = Evidence(importer.source(path, 'json').id)
            legacy = row.get('schema_version') == 1 and row.get('definition') == 'union_coverage_exact_interval_v1'
            if ((not legacy and (row.get('schema_version') != 2 or row.get('definition') != DEFINITION)) or
                row.get('method') != 'tvr_inclusive' or row.get('convention') != 'one_based_inclusive' or
                row.get('space') != 'nanotel_analyzed_read'):
                raise ValueError('unsupported coverage definition')
            fields = ('start','end','denominator_bp','canonical_bp','tvr_bp','overlap_bp','unassigned_bp','tvr_block_count')
            if any(type(row.get(k)) is not int or row[k] < 0 for k in fields):
                raise ValueError('invalid coverage counts')
            interval = read.calls['tvr_inclusive']['interval']
            if interval.status != A.AVAILABLE or (row['start']-1,row['end']) != (interval.value['start'],interval.value['end']):
                raise ValueError('Coverage uses an old/different boundary; regenerate coverage for the TVR-inclusive interval')
            n = row['denominator_bp']; c = row['canonical_bp']; t = row['tvr_bp']; overlap = row['overlap_bp']
            if n != row['end']-row['start']+1 or n <= 0 or max(c,t)>n or overlap>min(c,t) or row['unassigned_bp'] != n-c-t+overlap:
                raise ValueError('inconsistent coverage counts')
            for key, bases in [('canonical_pct',c),('tvr_pct',t)]:
                v=row.get(key)
                if type(v) not in (int,float) or not math.isfinite(v) or not math.isclose(v,100*bases/n,abs_tol=1e-7):
                    raise ValueError('inconsistent percentage')
            blocks = row.get('blocks')
            if not isinstance(blocks,list) or len(blocks)!=row['tvr_block_count']:
                raise ValueError('invalid block count')
            previous=row['start']-2; total=0
            for block in blocks:
                a,b=block.get('start'),block.get('end')
                if type(a) is not int or type(b) is not int or a<row['start'] or b>row['end'] or b<a or a<=previous+1:
                    raise ValueError('invalid or unmerged TVR blocks')
                total+=b-a+1;previous=b
            if total!=t:
                raise ValueError('TVR block lengths disagree with coverage')
            for key,field,unit in [('canonical_pct','canonical_pct','%'),('tvr_pct','tvr_pct','%'),
                    ('tvr_block_count','tvr_block_count','blocks'),('repeat_overlap_bp','overlap_bp','bp'),
                    ('repeat_unassigned_bp','unassigned_bp','bp')]:
                read.metrics[key]=Fact(A.AVAILABLE,row[field],unit=unit,population=DEFINITION,evidence=[ev])
            read.tracks['tvr_regions']=Fact(A.AVAILABLE,[dict(start=b['start']-1,end=b['end'],
                convention='zero_based_half_open',space='nanotel_analyzed_read') for b in blocks],evidence=[ev])
            read.evidence.append(ev)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            barcode.warnings.append(f'{path.name}: invalid coverage export: {exc}')
            for read in targets:
                for key in KEYS:
                    read.metrics[key]=unavailable('Invalid or conflicting coverage export',A.INVALID)
                read.tracks['tvr_regions']=unavailable('Invalid or conflicting coverage export',A.INVALID)
