"""Focused plotting checks run the real R analysis block on a tiny fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AnalysisPlotTests(unittest.TestCase):
    def test_r_plots_and_exports(self):
        rscript = os.environ.get("RSCRIPT") or shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript required; set RSCRIPT")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [rscript, "--vanilla", str(ROOT / "tests/analysis_plot_checks.R"),
                 str(ROOT / "dorado_workflow/data/NanoTel.R"), directory],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = Path(directory)
            for name in ("barcode01_telomere_plot", "barcode01_telomere_histogram", "empty_histogram"):
                html = (output / f"{name}.html").read_text(encoding="utf-8")
                self.assertIn("data:application/javascript;base64,", html)
                self.assertIn("Plotly.newPlot", html)
                figure = json.loads((output / f"{name}.plotly.json").read_text(encoding="utf-8"))
                self.assertIn("layout", figure)
            for name in ("barcode01_telomere_plot.png", "barcode01_telomere_histogram.png", "barcode01_telomere_histogram_pct.png"):
                self.assertTrue((output / name).read_bytes().startswith(b"\x89PNG"))
