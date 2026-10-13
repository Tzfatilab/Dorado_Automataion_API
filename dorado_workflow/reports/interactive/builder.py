"""Compatibility builder using the shared dashboard renderer."""
from pathlib import Path
from contextlib import nullcontext
from .models import validate
from ..storage.layout import atomic_text


def build_report(run, destination, results_root=None):
    """Write the current dashboard into a new/empty output directory.

    Both entry points use one renderer. The obsolete milestone UI and its
    duplicate browser assets are no longer shipped or maintained.
    """
    from ..overview.dashboard import render_screen
    validate(run)
    destination = Path(destination).resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FileExistsError('Report destination must be new or empty')
    from ..storage.archive import available_details
    # Archived barcode figure specifications are needed while rendering only.
    with available_details(results_root) if results_root is not None else nullcontext():
        page = render_screen(run, results_root=results_root)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'index.html'
    atomic_text(target, page)
    return target
