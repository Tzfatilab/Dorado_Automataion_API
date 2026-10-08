"""Read-only, offline presentation of existing NanoTel results (schema 1.0)."""

from .importers import import_results

__all__ = ["build_report", "import_results"]


def build_report(*args, **kwargs):
    """Import the HTML writer lazily; data import is independently usable."""
    from .builder import build_report as build
    return build(*args, **kwargs)
