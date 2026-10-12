"""Lossless storage for internal report exports, separate from user-facing plots."""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import hashlib
import os
import shutil
import tempfile
import zipfile

ARCHIVE = 'report_details.zip'


def digest(path):
    """Hash in bounded chunks, including large motif and density exports."""
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.digest()


def member_path(folder, name):
    """Reject archive traversal before creating files or removing sources."""
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe report archive member: ' + name)
    target = folder.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError('Report archive member escapes its folder')
    return target


@contextmanager
def available_details(root):
    """Temporarily expose archived exports to existing, unchanged data adapters.

    Loose files from a newer analysis take precedence. Only files created by
    this context and still byte-identical are removed afterwards, even on failure.
    """
    created = []
    directories = set()
    try:
        for archive in sorted(Path(root).rglob(ARCHIVE)):
            folder = archive.parent / 'report_details'
            with zipfile.ZipFile(archive) as source:
                names = source.namelist()
                if len(names) != len(set(names)):
                    raise ValueError('Duplicate report archive members')
                for info in source.infolist():
                    target = member_path(folder, info.filename)
                    if info.is_dir() or target.exists():
                        continue
                    parent = target.parent
                    while not parent.exists():
                        directories.add(parent)
                        parent = parent.parent
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Exclusive creation prevents overwriting a concurrent export.
                    with target.open('xb') as out:
                        try:
                            with source.open(info) as inp:
                                shutil.copyfileobj(inp, out, 1024 * 1024)
                        except Exception:
                            out.close()
                            target.unlink(missing_ok=True)
                            raise
                    created.append((target, digest(target)))
        yield
    finally:
        for path, checksum in created:
            if path.is_file() and digest(path) == checksum:
                path.unlink()
        for folder in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                try:
                    folder.rmdir()
                except PermissionError:
                    pass  # Windows/OneDrive may hold an empty directory open.


def pack_details(barcode):
    """Commit and CRC-check an archive before removing verified loose copies.

    Existing archived files are retained unless superseded by a loose export.
    Single-read images and scientific summary files are outside this directory.
    """
    barcode = Path(barcode).resolve()
    folder = barcode / 'report_details'
    if not folder.is_dir():
        return None
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    for path in files:
        if not path.resolve().is_relative_to(folder.resolve()) or path.is_symlink():
            raise ValueError('Report details contain a link outside the archive scope')
    if not files:
        return None
    checksums = {p: digest(p) for p in files}
    names = {p.relative_to(folder).as_posix() for p in files}
    archive = barcode / ARCHIVE
    fd, name = tempfile.mkstemp(prefix='report_details-', suffix='.tmp', dir=barcode)
    os.close(fd)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
            if archive.exists():
                with zipfile.ZipFile(archive) as old:
                    if len(old.namelist()) != len(set(old.namelist())):
                        raise ValueError('Duplicate archive members')
                    for info in old.infolist():
                        member_path(folder, info.filename)
                        if not info.is_dir() and info.filename not in names:
                            with old.open(info) as inp, out.open(info, 'w') as dst:
                                shutil.copyfileobj(inp, dst, 1024 * 1024)
            for path in files:
                # Already compressed CSV batches do not benefit from recompression.
                out.write(path, path.relative_to(folder).as_posix(),
                          compress_type=zipfile.ZIP_STORED if path.suffix == '.gz' else zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporary) as check:
            if check.testzip() is not None:
                raise ValueError('Report archive integrity check failed')
        if any(digest(p) != checksum for p, checksum in checksums.items()):
            raise RuntimeError('Report details changed during archival; source files retained')
        os.replace(temporary, archive)
        for path, checksum in checksums.items():
            if path.is_file() and digest(path) == checksum:
                path.unlink()
        # Remove empty directories only; never recursively delete user data.
        for directory in sorted((p for p in folder.rglob('*') if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            if not any(directory.iterdir()):
                try:
                    directory.rmdir()
                except PermissionError:
                    pass  # Archive is valid; an empty folder must not fail the run.
        if not any(folder.iterdir()):
            try:
                folder.rmdir()
            except PermissionError:
                pass
        return archive
    finally:
        temporary.unlink(missing_ok=True)
