"""Read immutable per-read exports in their original project without staging copies."""
import json
from dataclasses import dataclass
from pathlib import Path
import zipfile
from functools import lru_cache

from .archive import member_path

MANIFEST = "report_sources.json"


def source_folders(nanotel):
    path = Path(nanotel) / MANIFEST
    if path.is_file():
        info = path.stat()
        return dict(_source_folders(path, info.st_mtime_ns, info.st_size, False))
    # Completed recalculations keep internal source references in their unified
    # Excel instead of a separate JSON file in the user's results directory.
    for book in (Path(nanotel) / 'nanotel_results.xlsx', Path(nanotel).parent / 'nanotel_summary.xlsx'):
        if book.is_file():
            info = book.stat()
            return dict(_source_folders(book, info.st_mtime_ns, info.st_size, True))
    return {}


@lru_cache(maxsize=32)
def _source_folders(path, modified, size, workbook):
    if not workbook:
        saved = json.loads(path.read_text(encoding='utf-8'))
        return tuple((label, Path(folder)) for label, folder in saved.items())
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        if '_source_Report sources' not in book.sheetnames:
            return ()
        rows = iter(book['_source_Report sources'].values)
        if next(rows, ()) != ('Barcode', 'Original detail folder'):
            raise ValueError('Invalid saved report source references')
        saved = {}
        for label, folder in rows:
            if label in saved or not isinstance(label, str) or not isinstance(folder, str):
                raise ValueError('Invalid or duplicate saved report source reference')
            saved[label] = Path(folder)
        return tuple(saved.items())
    finally:
        book.close()


@dataclass(frozen=True)
class ArchivedDetail:
    """A read-only archive member with the filename operations used by adapters."""
    archive: Path
    member: str

    @property
    def path(self):
        return member_path(self.archive.parent / "report_details", self.member)

    @property
    def name(self):
        return self.path.name

    @property
    def parent(self):
        return self.path.parent

    def with_name(self, name):
        return ArchivedDetail(self.archive, str(Path(self.member).with_name(name)).replace("\\", "/"))

    def read_bytes(self):
        with zipfile.ZipFile(self.archive) as saved:
            return saved.read(self.member)

    def read_text(self, encoding="utf-8"):
        return self.read_bytes().decode(encoding)


def referenced_details(nanotel):
    """Discover detail exports only; old filtered populations and plots stay excluded."""
    for label, folder in sorted(source_folders(nanotel).items()):
        if not folder.is_dir():
            raise FileNotFoundError(f"Original NanoTel read details are unavailable: {folder}")
        details = folder / "report_details"
        loose = {p.relative_to(details).as_posix(): p for p in details.rglob("*") if p.is_file()}
        archive = folder / "report_details.zip"
        archived = {}
        if archive.is_file():
            with zipfile.ZipFile(archive) as saved:
                names = saved.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("Duplicate report archive members")
                for info in saved.infolist():
                    member_path(details, info.filename)
                    if not info.is_dir():
                        archived[info.filename] = ArchivedDetail(archive, info.filename)
        archived.update(loose)
        for name, path in sorted(archived.items()):
            if "telomere" not in name and not name.endswith(".html"):
                yield label, path
