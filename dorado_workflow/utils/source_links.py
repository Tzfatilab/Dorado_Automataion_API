"""Expose immutable source inputs without allocating another file copy."""
import os
from pathlib import Path


def link_source(source, destination) -> str:
    """Link an immutable input, returning its destination for copytree.

    Hard links share storage without depending on the original pathname.
    Symlinks also avoid copying, but require the original file to stay available.
    Neither kind prevents writes: callers must only read linked inputs and
    write regenerated outputs to different files.

    Args:
        source: Existing source artifact or source data.
        destination: Path where the new output is written.

    Returns:
        Destination path as a string; no file-content copy is created.
    """
    source, destination = Path(source).resolve(), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(str(destination))
    try:
        os.link(source, destination)
    except OSError:
        try:
            destination.symlink_to(source)
        except OSError as exc:
            raise OSError(
                "Cannot link saved input without copying it: " + str(source)
                + ". Choose an output folder on the source drive or enable file symlinks."
            ) from exc
    return str(destination)
