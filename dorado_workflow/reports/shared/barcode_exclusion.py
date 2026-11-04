"""Small, explicit per-barcode facts for offline overview selection."""
import json

from .short_telomeres import short_cutoff_bp
from ..overview.comparisons import comparison_data


def exclusion_payload(run, comparisons=None):
    """Per-barcode source records used to rebuild overview statistics after exclusion.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        Per-barcode source records used to rebuild overview statistics after exclusion.
    """
    comparisons = comparison_data(run) if comparisons is None else comparisons
    composition = {row['barcode']: row for row in comparisons['composition']}
    rows = []
    for barcode in run.barcodes:
        def value(key):
            """Available metric value, otherwise the enclosing adapter's missing-value marker.

            Args:
                key: Lookup key or field name.

            Returns:
                Available metric value, otherwise the enclosing adapter's missing-value marker.
            """
            fact = barcode.metrics.get(key)
            return fact.value if fact and fact.status == 'available' else None

        lengths = value('filtered_length_records')
        ids = {row['read_id'] for row in lengths or []}
        chromosomes = set()
        for read in barcode.reads:
            if read.id not in ids or read.alignments.status != 'available':
                continue
            names = {str(a['chromosome'].value) for a in read.alignments.value
                     if a.get('chromosome') and a['chromosome'].status == 'available'}
            if len(names) == 1:
                chromosomes.update(names)
        motif = composition.get(barcode.label)
        rows.append(dict(id=barcode.id, barcode_id=barcode.label,
                         total=value('total_reads'), filtered=value('amount_of_telomeres'),
                         population=getattr(barcode.metrics.get('amount_of_telomeres'), 'population', None),
                         length_population=getattr(barcode.metrics.get('filtered_length_records'), 'population', None),
                         lengths=[row['length_bp'] for row in lengths] if lengths is not None else None,
                         chromosomes=sorted(chromosomes), cutoff=short_cutoff_bp(run.settings, barcode),
                         composition={key: motif[key] for key in ('base_counts', 'total', 'with_tvr')} if motif else None))
    return rows


def exclusion_data_html(run, comparisons=None):
    """Exclusion data html.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        HTML markup for exclusion data html.
    """
    payload = json.dumps(exclusion_payload(run, comparisons=comparisons), ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
    return '<script type="application/json" id="barcode-exclusion-data">' + payload + '</script>'
