"""Convert explicitly exported query spans to NanoTel's analyzed orientation."""
from .coordinates import integer
from .models import Availability as A, Fact, unavailable


def query_alignment(row, read_length, reversed_read, evidence):
    missing = unavailable('Aligned query span or analyzed-read orientation was not exported')
    result = {'query_interval': missing, 'query_strand': missing}
    if (row.get('alignment_query_convention') != 'zero_based_half_open'
            or row.get('alignment_query_space') != 'original_read'
            or type(reversed_read) is not bool):
        return result
    try:
        start = integer(row.get('alignment_query_start'))
        end = integer(row.get('alignment_query_end'))
        length = integer(row.get('alignment_query_length'))
        strand = row.get('alignment_direction')
        if length != read_length or not 0 <= start < end <= length or strand not in {'+', '-'}:
            raise ValueError('Query coordinates or length disagree with the analyzed read')
        if reversed_read:
            start, end = length-end, length-start
            strand = '+' if strand == '-' else '-'
        result['query_interval'] = Fact(A.AVAILABLE, dict(start=start, end=end,
            convention='zero_based_half_open', space='nanotel_analyzed_read'),
            unit='bp', origin='presentation_aggregate', evidence=evidence)
        result['query_strand'] = Fact(A.AVAILABLE, strand, evidence=evidence,
                                      origin='presentation_aggregate')
    except (ValueError, TypeError, OverflowError):
        result = {key: unavailable('Invalid exported query coordinates', A.INVALID) for key in result}
    return result
