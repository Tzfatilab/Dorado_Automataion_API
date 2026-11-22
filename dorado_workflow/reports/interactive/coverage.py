"""Import versioned R coverage measurements; never calculate coverage here."""
import json
import math
import re
from .models import Availability as A, Evidence, Fact, unavailable
from .identities import ReadIndex

DEFINITION = 'union_coverage_tvr_interval_v2'
KEYS = ('canonical_pct', 'tvr_pct', 'tvr_bp', 'repeat_overlap_bp', 'repeat_unassigned_bp', 'tsq_pct', 'tsq_bp')


def import_coverage(importer, barcode):
    """Validate source identity, denominator, coverage consistency.

    Args:
        importer: ResultImporter providing saved tables and source provenance.
        barcode: Imported Barcode record containing reads, metrics and evidence.

    Returns:
        None.
    """
    index = ReadIndex(barcode.reads)
    for read in barcode.reads:
        for key in KEYS:
            read.metrics[key] = unavailable('Versioned NanoTel coverage export not available')
    seen = set()
    exports = []
    for read in barcode.reads:
        fact = read.metrics.get('_repeat_coverage_export')
        if fact and fact.status == A.AVAILABLE:
            exports.append(('summary coverage', fact.value, fact.evidence[0], read))
    for path in importer.files('*read*_coverage.json'):
        if path.parent.name != 'report_details' or not (path.name.startswith(barcode.label+'_read') or
                (re.fullmatch(r'read\d+_coverage.json', path.name) and path.parent.parent.name.lower() == barcode.label.lower())):
            continue
        exports.append((path.name, path.read_text(encoding='utf-8-sig'), Evidence(importer.source(path, 'json').id), None))
    for name, encoded, ev, source_read in exports:
        targets = []
        try:
            row = json.loads(encoded)
            serial = re.search(r'(?:^|_)read(\d+)_', name)
            targets = ([source_read] if source_read and
                       source_read.original_id.split()[0] == (str(row.get('read_id') or '').split() or [''])[0]
                       else index.find(row.get('read_id'), serial[1] if serial else row.get('Serial')))
            if len(targets) != 1:
                raise ValueError('unmatched or ambiguous read identity')
            read = targets[0]
            if read.id in seen:
                raise ValueError('duplicate coverage exports')
            seen.add(read.id)
            legacy = row.get('schema_version') == 1 and row.get('definition') == 'union_coverage_exact_interval_v1'
            if ((not legacy and (row.get('schema_version') != 2 or row.get('definition') != DEFINITION)) or
                row.get('method') != 'tvr_inclusive' or row.get('convention') != 'one_based_inclusive' or
                row.get('space') != 'nanotel_analyzed_read'):
                raise ValueError('unsupported coverage definition')
            fields = ('start','end','denominator_bp','canonical_bp','tvr_bp','overlap_bp','unassigned_bp')
            if any(type(row.get(k)) is not int or row[k] < 0 for k in fields):
                raise ValueError('invalid coverage counts')
            interval = read.calls['tvr_inclusive']['interval']
            if interval.status != A.AVAILABLE or (row['start']-1,row['end']) != (interval.value['start'],interval.value['end']):
                raise ValueError('Coverage uses an old/different boundary; regenerate coverage for the TVR-inclusive interval')
            n = row['denominator_bp']; c = row['canonical_bp']; t = row['tvr_bp']; overlap = row['overlap_bp']
            # Inclusion-exclusion accounts for bases covered by both motif roles.
            if n != row['end']-row['start']+1 or n <= 0 or max(c,t)>n or overlap>min(c,t) or row['unassigned_bp'] != n-c-t+overlap:
                raise ValueError('inconsistent coverage counts')
            for key, bases in [('canonical_pct',c),('tvr_pct',t)]:
                v=row.get(key)
                if type(v) not in (int,float) or not math.isfinite(v) or not math.isclose(v,100*bases/n,abs_tol=1e-7):
                    raise ValueError('inconsistent percentage')
            for key,field,unit in [('canonical_pct','canonical_pct','%'),('tvr_pct','tvr_pct','%'),
                    ('tvr_bp','tvr_bp','bp'),('repeat_overlap_bp','overlap_bp','bp'),
                    ('repeat_unassigned_bp','unassigned_bp','bp')]:
                read.metrics[key]=Fact(A.AVAILABLE,row[field],unit=unit,population=DEFINITION,evidence=[ev])
            if 'tsq_bp' in row or 'ordinary_tvr_bp' in row:
                s, t = row.get('tsq_bp'), row.get('ordinary_tvr_bp')
                if (type(s) is not int or type(t) is not int or min(s, t) < 0
                        or s + t != row['tvr_bp'] or not isinstance(row.get('tsq_pattern'), str)):
                    raise ValueError('inconsistent separate TSQ/TVR coverage')
                for prefix, bases in [('tsq', s), ('tvr', t)]:
                    read.metrics[prefix+'_bp'] = Fact(A.AVAILABLE, bases, unit='bp', evidence=[ev])
                    read.metrics[prefix+'_pct'] = Fact(A.AVAILABLE, 100*bases/n, unit='%', evidence=[ev])
            read.evidence.append(ev)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            barcode.warnings.append(f'{name}: invalid coverage export: {exc}')
            for read in targets:
                for key in KEYS:
                    read.metrics[key]=unavailable('Invalid or conflicting coverage export',A.INVALID)
