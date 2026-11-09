"""Explicit opt-in rules for KM execution and report visibility."""


def km_requested(settings):
    """KM is opt-in for every organism, including Human."""
    return settings.get('include_km') is True


def show_km(run):
    """Show KM only when the saved analysis settings explicitly enable it."""
    if run.settings.status != 'available':
        return False
    settings = run.settings.value
    if not isinstance(settings, dict):
        return False
    params = settings.get('nanotel_analysis', settings.get('nanotel', settings))
    return isinstance(params, dict) and km_requested(params)
