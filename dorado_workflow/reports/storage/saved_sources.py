"""Read immutable per-read exports in their original project without staging copies."""
import json
from dataclasses import dataclass
from pathlib import Path
import zipfile

from .archive import member_path

MANIFEST = "report_sources.json"


def source_folders(nanotel):
    path = Path(nanotel) / MANIFEST
    if not path.is_file():
        return {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    return {label: Path(folder) for label, folder in saved.items()}


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
