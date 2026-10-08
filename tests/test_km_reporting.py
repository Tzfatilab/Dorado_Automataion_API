"""Bioconda-stage KM checks; set RSCRIPT when Rscript is not on PATH."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KMReportingTests(unittest.TestCase):
    def test_r_checks_and_barcode_reports(self):
        rscript = os.environ.get("RSCRIPT") or shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript required; set RSCRIPT")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [rscript, "--vanilla", str(ROOT / "tests/km_reporting_checks.R"),
                 str(ROOT / "dorado_workflow/data/NanoTel.R"), directory],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = Path(directory)
            report = (output / "reportable_results.txt").read_text(encoding="utf-8")
            self.assertIn("5,000 bp", report)
            self.assertIn("4,500\u20135,500 bp", report)
            self.assertIn("20.0%", report)
            for name in ("too_wide", "non_estimable", "failed"):
                with self.subTest(name=name):
                    report = (output / f"{name}_results.txt").read_text(encoding="utf-8")
                    self.assertIn("Not reported", report)
                    self.assertIn("KM Reporting Reason", report)
                    self.assertIn("5,990 bp", report)
                    for hidden in ("5,000", "4,400", "5,600", "5,500"):
                        self.assertNotIn(hidden, report)


if __name__ == "__main__":
    unittest.main()
