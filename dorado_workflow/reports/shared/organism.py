"""Organism-dependent presentation rules for the dashboard."""


def show_km(run):
    """Show KM and completeness only for an explicitly recorded non-human run.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.

    Returns:
        True when a recorded nonhuman organism permits the KM panel.
    """
    organism = run.organism
    if organism.status != 'available' or not isinstance(organism.value, str):
        return False
    name = organism.value.strip().casefold()
    return bool(name) and name not in {'human', 'homo sapiens'}
