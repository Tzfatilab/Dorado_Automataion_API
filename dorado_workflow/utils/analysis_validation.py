"""Validate analysis settings without changing defaults or coercing values."""
import math
from numbers import Real


def validate_nanotel_settings(settings):
    """Reject nonfinite/out-of-range supplied values; absent settings keep defaults."""
    ranges = {
        'min_density': (0, 1, False), 'density_threshold': (0, 1, False),
        'max_mismatch': (0, 1, True),
        'short_telomere_threshold_bp': (1, None, True),
        'min_read_length': (0, None, True), 'read_length': (0, None, True),
        'max_telomere_start': (0, None, True), 'max_edge_distance': (0, None, True),
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
