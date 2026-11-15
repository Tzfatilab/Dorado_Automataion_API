"""Explicit opt-in rules for KM execution and report visibility."""
import re


def km_requested(settings):
    """KM is opt-in for every organism, including Human."""
    return isinstance(settings, dict) and settings.get('include_km') is True


def show_km(run):
    """Show KM only when the saved analysis settings explicitly enable it."""
    if run.settings.status != 'available':
        return False
    settings = run.settings.value
    if not isinstance(settings, dict):
        return False
    params = settings.get('nanotel_analysis', settings.get('nanotel', settings))
    return isinstance(params, dict) and km_requested(params)


def is_km_field(name):
    name = str(name).casefold().removeprefix('nanotel_final_')
    return name.startswith('km_') or name in {
        'event', 'completeness', 'read_completeness', 'complete_telomeric_reads',
        'incomplete_telomeric_reads', 'censoring_rate_pct',
    }


def without_km(value):
    """Omit optional KM/completeness facts from a published copy."""
    if isinstance(value, dict):
        value = {key: without_km(item) for key, item in value.items() if not is_km_field(key)}
        if isinstance(value.get('data'), list) and isinstance(value.get('layout'), dict):
            from ..barcode.length_plots import _hide_completeness
            _hide_completeness(value)
        return value
    if isinstance(value, list):
        return [without_km(item) for item in value]
    return value


def km_table(name):
    name = name.removeprefix('_source_')
    return name in {'Kaplan-Meier', 'KM by barcode', 'KM run statistics'} or bool(re.fullmatch(r'km_barcode\d+', name))
