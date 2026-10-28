"""Read NanoTel final-filter exports when R post-analysis output is absent."""
from statistics import median
from .models import Availability as A, unavailable

POPULATION = 'NanoTel final-filtered reads'


def import_final_population(importer, barcode, number):
    """Reuse exported counts/lengths; never repeat the scientific filters.

    Use the recorded exact/mismatch mode. Legacy files without that setting
    are accepted only when both modes agree row by row.
    """
    for target, source in [('amount_of_telomeres', 'number_of_telomeric_reads_post_filtration'),
                           ('median_telomere_length', 'median_telomeric_length_post_filtration_bp')]:
        fact = barcode.metrics.get('nanotel_final_' + source)
        if fact and fact.status == A.AVAILABLE:
            barcode.metrics[target] = fact
    paths = importer.files(barcode.label + '_filtered_sorted_summary.csv')
    if len(paths) != 1:
        return
    table = importer.csv_table(paths[0])
    from ..reads.density import mismatch_enabled
    from .models import Fact
    mode = mismatch_enabled(Fact(A.AVAILABLE, importer.metadata.get('settings')))
    if mode is None:
        for row, ev in table[1]:
            exact = number(row, 'Telomere_length', ev, unit='bp')
            mismatch = number(row, 'Telomere_length_mismatch', ev, unit='bp')
            if exact.status != A.AVAILABLE or mismatch.status != A.AVAILABLE or exact.value != mismatch.value:
                barcode.metrics['filtered_length_records'] = unavailable(
                    'NanoTel matching mode is not recorded and exact/mismatch lengths differ')
                return
    field = 'Telomere_length_mismatch' if mode is True else 'Telomere_length'
    importer.filtered_lengths(barcode, table, field, POPULATION)
    lengths = barcode.metrics['filtered_length_records']
    reported = barcode.metrics.get('median_telomere_length', unavailable('Median not exported'))
    if lengths.status == reported.status == A.AVAILABLE and lengths.value:
        if abs(median(r['length_bp'] for r in lengths.value) - reported.value) > 0.001:
            barcode.metrics['filtered_length_records'] = unavailable(
                'NanoTel filtered lengths disagree with the exported median', A.INVALID)
