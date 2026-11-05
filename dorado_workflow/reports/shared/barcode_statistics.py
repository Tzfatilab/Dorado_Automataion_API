"""Shared barcode Key Statistics for cards, summary tables and workbooks."""
import json
from ..reads.density import tvr_enabled


def mismatch_statistics(barcode, composition=None):
    """Read mismatch counts from the complete post-filtered composition.

    Args:
        barcode: Barcode record used to distinguish empty from missing populations.
        composition: Saved-hit mismatch summary for this barcode, or None.

    Returns:
        Counts of reads with mismatch hits and distinct observed mismatch sequences;
        missing evidence remains None, while an explicitly empty population is zero.
    """
    population = barcode.metrics.get('filtered_length_records')
    if population and population.status == 'available' and not population.value:
        return dict(reads_with_mismatch=0, mismatch_patterns=0)
    return dict(
        reads_with_mismatch=composition['with_mismatch'] if composition is not None else None,
        mismatch_patterns=len(composition['motifs']) if composition is not None else None)


def tvr_statistics(barcode, settings, composition=None):
    """Count TVR-positive filtered reads and distinct observed motifs.

    Disabled analysis is different from missing evidence. A motif count is
    withheld when exported coverage cannot identify all observed motif names.

    Args:
        barcode: Imported Barcode record containing reads, metrics and evidence.
        settings: Recorded analysis settings and their availability.
        composition: Precomputed TVR composition for this barcode, when supplied. Default: None.

    Returns:
        TVR-positive read and observed-motif counts, with explicit missing/disabled states.
    """
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
    """Read the shared barcode card/table values without changing populations.

    Args:
        barcode: Imported Barcode record containing reads, metrics and evidence.
        settings: Recorded analysis settings and their availability.
        cells: Chromosome summary records grouped by barcode.
        composition: Precomputed TVR composition for this barcode, when supplied. Default: None.

    Returns:
        Key Statistics values for one barcode, preserving missing values.
    """
    def value(key):
        """Available metric value, otherwise the enclosing adapter's missing-value marker.

        Args:
            key: Lookup key or field name.

        Returns:
            Available metric value, otherwise the enclosing adapter's missing-value marker.
        """
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
