"""Write a portable file:// report, without changing source artifacts."""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import tempfile

from .models import Run, validate
from .dashboard import dashboard_data


def payload(value):
    """Serialize data as a script-safe JSON literal, never executable source input."""
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def build_report(run: Run, destination) -> Path:
    """Build atomically into a new/empty directory; never delete an existing report.

    One local script per barcode avoids loading every molecule on the run page.
    Scripts use fixed hash filenames; scientific names are data, never paths.
    """
    validate(run)
    from plotly.offline import get_plotlyjs
    destination = Path(destination).resolve()
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise FileExistsError("Report destination must be new or empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nanotel-report-", dir=destination.parent) as temp:
        staged = Path(temp) / "report"
        assets = staged / "assets"
        data_dir = assets / "data"
        data_dir.mkdir(parents=True)
        templates = Path(__file__).parent / "assets"
        shutil.copyfile(templates / "index.html", staged / "index.html")
        for name in ("report.css", "report.js"):
            shutil.copyfile(templates / name, assets / name)
        (assets / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
        index = asdict(run)
        index["dashboard"] = dashboard_data(run)
        for barcode in index["barcodes"]:
            full = dict(barcode)
            barcode.pop("reads")
            (data_dir / (barcode["id"] + ".js")).write_text(
                "window.NanoTelData.barcodes[" + payload(barcode["id"]) + "]=" + payload(full) + ";\n",
                encoding="utf-8")
        (data_dir / "run.js").write_text(
            "window.NanoTelData={run:" + payload(index) + ",barcodes:Object.create(null)};\n", encoding="utf-8")
        # A complete machine-readable copy supports inspection and downstream validation.
        full_document = asdict(run)
        full_document["dashboard"] = index["dashboard"]
        (staged / "report-data.json").write_text(json.dumps(full_document, ensure_ascii=True, allow_nan=False, indent=2), encoding="utf-8")
        if destination.exists():
            destination.rmdir()  # Only the previously verified empty directory.
        staged.rename(destination)
    return destination / "index.html"
