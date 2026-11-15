"""Validate analysis settings without changing defaults or coercing values."""
import math
import re
from numbers import Real


def parse_tvr_patterns(value):
    """Normalize manual DNA motifs separated by commas, semicolons or whitespace."""
    return [pattern.upper() for pattern in re.split(r'[,;\s]+', str(value or '').strip()) if pattern]


def validate_tvr_patterns(patterns, canonical=None):
    """Apply the same motif rules in manual input and workflow configuration."""
    if not isinstance(patterns, list) or any(
        not isinstance(pattern, str) or len(pattern) < 5
        or any(base not in 'ACGT' for base in pattern) for pattern in patterns
    ):
        raise ValueError('Each TVR sequence must contain at least 5 bases, using only A, C, G and T.')
    if canonical:
        canonical = canonical.upper()
        reverse = canonical.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
        repeated = sorted(set(patterns) & {canonical, reverse})
        if repeated:
            raise ValueError('Remove canonical telomere repeats from the TVR list: '
                             + ', '.join(repeated) + '. They are already analyzed as canonical repeats.')


def validate_nanotel_settings(settings):
    """Reject nonfinite/out-of-range supplied values; absent settings keep defaults.

    Args:
        settings: Recorded analysis settings and their availability.

    Returns:
        None.
    """
    if "include_km" in settings and type(settings["include_km"]) is not bool:
        raise ValueError("include_km must be true or false.")
    if "tvr_patterns" in settings:
        validate_tvr_patterns(settings['tvr_patterns'])
    ranges = {
        'min_density': (0, 1, False), 'density_threshold': (0, 1, False),
        'max_mismatch': (0, 1, True),
        'short_telomere_threshold_bp': (1, None, True),
        'min_read_length': (0, None, True), 'read_length': (0, None, True),
        'max_telomere_start': (0, None, True), 'max_edge_distance': (0, None, True),
        'display_max_edge_distance': (0, None, True),
    }
    for name, (minimum, maximum, integer) in ranges.items():
        if name not in settings:
            continue
        value = settings[name]
        # None is the supported way to disable optional minimum-length filtering.
        if value is None and name in {'min_read_length', 'read_length'}:
            continue
        if (isinstance(value, bool) or not isinstance(value, Real)
                or not math.isfinite(value) or value < minimum
                or (maximum is not None and value > maximum)
                or (integer and int(value) != value)):
            unit = 'base pairs' if name not in {'min_density', 'density_threshold', 'max_mismatch'} else 'unitless'
            limit = f'{minimum} to {maximum}' if maximum is not None else f'at least {minimum}'
            raise ValueError(f'Invalid NanoTel setting {name}={value!r}: expected '
                             f'a finite {"integer" if integer else "number"}, {limit} ({unit})')
