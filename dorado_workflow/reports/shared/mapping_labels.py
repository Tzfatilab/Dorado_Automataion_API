"""Display chromosome ends without changing source reference identifiers."""
import re


def mapping_labels(reference, organism):
    """Return the display reference and its paired arm, when explicitly labeled."""
    reference = str(reference or '')
    match = re.fullmatch(r'(chr(?:[0-9]+|X|Y|M|MT))_(Head|Tail|p|q)', reference, re.IGNORECASE)
    if not match:
        return reference, None
    end = match[2].lower()
    mammal = str(organism or '').strip().casefold() in {'human', 'homo sapiens', 'mouse', 'mus musculus'}
    arm = {'head': 'p', 'tail': 'q'}.get(end, end) if mammal else {'head': 'Head', 'tail': 'Tail'}.get(end, end)
    return match[1] + '_' + arm, arm


def annotate_alignment(alignment, organism, evidence):
    """Attach display labels while retaining the original mapped reference."""
    from ..interactive.models import Fact, Availability as A
    reference = alignment.get('reference')
    if not reference or reference.status != A.AVAILABLE:
        return
    display, arm = mapping_labels(reference.value, organism)
    alignment['display_reference'] = Fact(A.AVAILABLE, display, evidence=evidence,
                                         origin='presentation_aggregate')
    if arm:
        alignment['arm'] = Fact(A.AVAILABLE, arm, evidence=evidence,
                               origin='presentation_aggregate', population='source reference chromosome end')


def chromosome_ends(barcode):
    """Distinct explicit ends from unambiguous retained read assignments."""
    records = barcode.metrics.get('filtered_length_records')
    if not records or records.status != 'available':
        return None
    retained = {row['read_id'] for row in records.value}
    ends = set()
    for read in barcode.reads:
        if read.id not in retained or read.alignments.status != 'available':
            continue
        assignments = set()
        complete = bool(read.alignments.value)
        for alignment in read.alignments.value:
            chromosome, arm = alignment.get('chromosome'), alignment.get('arm')
            if not chromosome or not arm or chromosome.status != 'available' or arm.status != 'available':
                complete = False
                continue
            assignments.add((str(chromosome.value), str(arm.value)))
        if complete and len(assignments) == 1:
            ends.update(chromosome + '_' + arm for chromosome, arm in assignments)
    return sorted(ends) if ends or not retained else None
