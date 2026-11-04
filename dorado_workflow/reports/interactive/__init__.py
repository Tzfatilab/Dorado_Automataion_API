"""Read-only, offline presentation of existing NanoTel results (schema 1.0)."""

from .importers import import_results

__all__ = ["build_report", "import_results"]


def build_report(*args, **kwargs):
    """Import the HTML writer lazily; data import is independently usable.

    Args:
        args: Command-line arguments or forwarded positional arguments.
        kwargs: Keyword arguments forwarded to the underlying operation.

    Returns:
        Path to the generated HTML entry point.
    """
    from .builder import build_report as build
    return build(*args, **kwargs)
