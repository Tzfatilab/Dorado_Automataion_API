"""Verified reference annotations supplied alongside a run's results."""
import re
from .models import Availability as A, Fact, unavailable


def reference_annotation(importer, reference):
    """Require one exact reference match; never infer p/q from Head/Tail names.

    The user supplies RESULTS/reference_annotations.csv with reference,
    chromosome and arm columns. Duplicate/conflicting rows remain invalid.
    """
    if not hasattr(importer, '_reference_annotations'):
        importer._reference_annotations={}
        path=importer.root/'reference_annotations.csv'
        if path.is_file():
            _, rows, _=importer.csv_table(path)
            for row,ev in rows:
                key=row.get('reference');chrom=row.get('chromosome');arm=row.get('arm')
                if not key:
                    continue
                if key in importer._reference_annotations or not re.fullmatch(r'chr(?:[0-9]+|X|Y|M|MT)',chrom or '') or arm not in ('p','q'):
                    importer._reference_annotations[key]={'chromosome':unavailable('Invalid or duplicate reference annotation',A.INVALID),
                        'arm':unavailable('Invalid or duplicate reference annotation',A.INVALID)}
                else:
                    importer._reference_annotations[key]={'chromosome':Fact(A.AVAILABLE,chrom,evidence=[ev]),
                        'arm':Fact(A.AVAILABLE,arm,evidence=[ev])}
    return importer._reference_annotations.get(reference,{})
