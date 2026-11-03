"""Shared barcode Key Statistics for cards, summary tables and workbooks."""
import json
from ..reads.density import tvr_enabled


def tvr_statistics(barcode, settings, composition=None):
    if tvr_enabled(settings) is False:
        return dict(with_tvr='Not requested', motifs='Not requested')
    population=barcode.metrics.get('filtered_length_records')
    if not population or population.status!='available':
        return dict(with_tvr=None,motifs=None)
    if not population.value:
        return dict(with_tvr=0,motifs=0)
    if composition is not None:
        return dict(with_tvr=composition['with_tvr'],motifs=len(composition['motifs']))
    by_id={read.id:read for read in barcode.reads}
    options=settings.value.get('nanotel_analysis',settings.value) if settings and settings.status=='available' else {}
    patterns=options.get('tvr_patterns')
    single=patterns[0] if isinstance(patterns,list) and len(set(patterns))==1 else None
    count=0;motifs=set();complete_motifs=True
    for record in population.value:
        read=by_id.get(record['read_id'])
        fact=read.metrics.get('tvr_pct') if read else None
        if not fact or fact.status!='available':
            return dict(with_tvr=None,motifs=None)
        if fact.value<=0:
            continue
        count+=1
        saved=read.metrics.get('_repeat_coverage_export')
        names=None
        if saved and saved.status=='available':
            try:
                names=json.loads(saved.value).get('tvr_motifs')
            except (ValueError,TypeError):
                pass
        if isinstance(names,list) and names and all(isinstance(name,str) and name in (patterns or []) for name in names):
            motifs.update(names)
        elif single:
            # Positive validated TVR coverage from a single recorded search motif
            # identifies that motif. Never count unobserved configured motifs.
            motifs.add(single)
        else:
            complete_motifs=False
    return dict(with_tvr=count,motifs=len(motifs) if complete_motifs else None)


def barcode_key_statistics(barcode, settings, cells, composition=None):
    """Read the shared barcode card/table values without changing populations."""
    def value(key):
        fact = barcode.metrics.get(key)
        return fact.value if fact and fact.status == 'available' else None

    tvr = tvr_statistics(barcode, settings, composition)
    chromosomes = {cell['chromosome'] for cell in cells
                   if cell['barcode'] == barcode.label}
    post_filtered = value('amount_of_telomeres')
    return {
        'total_reads': value('total_reads'),
        'post_filtered_reads': post_filtered,
        'median_length_bp': value('median_telomere_length'),
        'reads_with_tvr': tvr['with_tvr'],
        'tvr_motifs': tvr['motifs'],
        'chromosomes': len(chromosomes) if chromosomes else 0 if post_filtered == 0 else None,
    }
