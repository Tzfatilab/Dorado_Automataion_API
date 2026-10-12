"""Explicit recovery of coverage exports from completed, saved motif searches.

No sequence search or boundary calling is repeated. This opt-in repair uses the
same clipped interval unions as NanoTel's report_repeat_coverage function.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from .output_layout import atomic_text


def union(ranges):
    """Merge overlapping and adjacent 1-based inclusive intervals."""
    result = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1] + 1:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def coverage(read_id, start, end, hits):
    """Clip each category, retaining overlap and unmatched bases explicitly."""
    groups = {role: union((max(a, start), min(b, end)) for a, b in hits[role]
                         if a <= end and b >= start) for role in ('canonical', 'tvr')}
    size = lambda ranges: sum(b-a+1 for a, b in ranges)
    c, t = size(groups['canonical']), size(groups['tvr'])
    overlap = c + t - size(union(groups['canonical'] + groups['tvr']))
    n = end-start+1
    return dict(schema_version=2, definition='union_coverage_tvr_interval_v2',
                read_id=read_id, method='tvr_inclusive', convention='one_based_inclusive',
                space='nanotel_analyzed_read', start=start, end=end, denominator_bp=n,
                canonical_bp=c, tvr_bp=t, overlap_bp=overlap, unassigned_bp=n-c-t+overlap,
                canonical_pct=100*c/n, tvr_pct=100*t/n, tvr_block_count=len(groups['tvr']),
                blocks=[dict(start=a, end=b) for a, b in groups['tvr']])


def _recover_barcode(folder):
    """Validate compact exports before replacing any existing coverage file."""
    folder = Path(folder)
    details = folder / 'report_details'
    summary = folder / (folder.name + '_summary.csv')
    index = details / (folder.name + '_reads_index.csv.gz')
    motifs = details / (folder.name + '_reads_motifs.csv.gz')
    with gzip.open(index, 'rt', encoding='utf-8-sig', newline='') as stream:
        identities = {}
        for row in csv.DictReader(stream):
            key = row['read_key']
            if row['schema_version'] != '2' or key in identities:
                raise ValueError('Invalid or duplicate compact read identity')
            identities[key] = row['read_id']
    if len(set(identities.values())) != len(identities):
        raise ValueError('Ambiguous read identities')
    records = {}
    with summary.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            key = row['Serial']
            if key in records or identities.get(key) != row['sequence_ID']:
                raise ValueError('Summary and motif identities disagree')
            start, end = int(row['Telomere_start_mismatch_tvr']), int(row['Telomere_end_mismatch_tvr'])
            if start < 1 or end < start:
                continue  # No valid TVR-inclusive call was exported for this read.
            if end > int(row['sequence_length']):
                raise ValueError('Boundary exceeds read length')
            records[key] = dict(start=start, end=end, length=int(row['sequence_length']),
                                hits={'canonical': [], 'tvr': []}, complete=False)
    # Stream compact data without expanding three methods or loading density data.
    with gzip.open(motifs, 'rt', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            methods = row['method'].split('|')
            if 'tvr_inclusive' not in methods:
                continue
            key = row['read_id']
            if key not in identities:
                raise ValueError('Unknown motif read identity')
            if key not in records:
                continue
            target = records[key]
            if (row['schema_version'] != '2' or len(methods) != len(set(methods))
                    or row['convention'] != 'one_based_inclusive'
                    or row['space'] != 'nanotel_analyzed_read'):
                raise ValueError('Unsupported motif coordinates or schema')
            if row['record_type'] == 'search_complete':
                if target['complete']:
                    raise ValueError('Duplicate completion marker')
                target['complete'] = True
            elif row['record_type'] == 'match':
                a, b = int(row['start']), int(row['end'])
                if (row['role'] not in target['hits'] or not 1 <= a <= b <= target['length']
                        or len(row['matched_sequence']) != b-a+1):
                    raise ValueError('Invalid motif hit')
                target['hits'][row['role']].append((a, b))
            else:
                raise ValueError('Unknown motif record type')
    if any(not row['complete'] for row in records.values()):
        raise ValueError('Incomplete motif searches; no coverage files were changed')
    # Preserve originals once, outside the importer discovery pattern.
    backup = details / 'coverage_before_recovery'
    backup.mkdir(exist_ok=True)
    for key, row in records.items():
        path = details / ('read' + str(int(key)) + '_coverage.json')
        original = backup / (path.name + '.bak')
        if path.exists() and not original.exists():
            original.write_bytes(path.read_bytes())
        result = coverage(identities[key], row['start'], row['end'], row['hits'])
        result['recovered_from'] = [summary.name, motifs.name, index.name]
        atomic_text(path, json.dumps(result, indent=2))
    # Record input hashes so the replacement exports remain auditable.
    sources = []
    for path in (summary, motifs, index):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        sources.append(dict(file=path.name, sha256=digest.hexdigest()))
    atomic_text(details / 'coverage_recovery.json', json.dumps(dict(
        definition='union_coverage_tvr_interval_v2', reads=len(records), sources=sources), indent=2))
    return len(records)


def recover_barcode(folder):
    """Support both legacy loose exports and the compact barcode archive."""
    from .detail_archive import available_details, pack_details
    folder = Path(folder)
    archived = (folder / 'report_details.zip').exists()
    with available_details(folder):
        count = _recover_barcode(folder)
    if archived:
        pack_details(folder)
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('barcode_folder', type=Path)
    args = parser.parse_args()
    print(f'Recovered coverage for {recover_barcode(args.barcode_folder)} reads', flush=True)
