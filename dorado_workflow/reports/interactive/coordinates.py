"""Explicit coordinate conversion only; never infer a biological boundary."""
from .models import Availability as A, Fact, unavailable


def integer(value):
    """Integral numeric value; invalid coordinates raise an exception.

    Args:
        value: Value to inspect, convert or format.

    Returns:
        Integral numeric value; invalid coordinates raise an exception.
    """
    if isinstance(value, bool):
        raise ValueError("Boolean is not a coordinate")
    number = float(value)
    if not number.is_integer():
        raise ValueError("Expected an integer")
    return int(number)


def normalize_interval(start, end, *, convention, space, evidence, length=None):
    """Retain raw coordinates and normalize within the same axis/orientation.

    NanoTel R intervals are 1-based inclusive on the analyzed sequence. This
    does not establish their orientation relative to the original FASTQ read.

    Args:
        start: Interval start in the declared coordinate convention.
        end: Interval end in the declared coordinate convention.
        convention: Declared coordinate convention.
        space: Coordinate axis to which the interval belongs.
        evidence: Source references supporting the returned measurement.
        length: Sequence or coordinate-space length in base pairs. Default: None.

    Returns:
        Dictionary containing original coordinates and a normalized interval Fact.
    """
    # Preserve the original endpoints and their declared coordinate convention
    # alongside normalized values so users can trace every conversion.
    raw = {"start": start, "end": end, "convention": convention, "space": space}
    if convention not in {"one_based_inclusive", "zero_based_half_open"}:
        normalized = unavailable("Source coordinate convention is unknown")
    elif start in (None, "", "NA", "NaN") or end in (None, "", "NA", "NaN"):
        normalized = unavailable("No interval exported")
    else:
        try:
            a, b = integer(start), integer(end)
            if convention == "one_based_inclusive":
                # [1, 6] inclusive becomes [0, 6) half-open: only start shifts.
                a -= 1
            if a < 0 or b <= a or (length is not None and b > length):
                raise ValueError("Interval outside its coordinate space")
            normalized = Fact(A.AVAILABLE, {"start": a, "end": b,
                "convention": "zero_based_half_open", "space": space}, unit="bp", evidence=evidence)
        except (ValueError, TypeError, OverflowError) as exc:
            normalized = unavailable(str(exc), A.INVALID)
    return {"raw": Fact(A.AVAILABLE, raw, evidence=evidence), "normalized": normalized}
