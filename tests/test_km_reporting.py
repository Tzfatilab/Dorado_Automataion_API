"""Bioconda-stage KM checks; set RSCRIPT when Rscript is not on PATH."""
import os
import csv
import json
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
            for name in ("reportable", "too_wide", "non_estimable", "failed"):
                with self.subTest(export=name):
                    data = json.loads((output / f"{name}_analysis.json").read_text(encoding="utf-8"))
                    self.assertEqual(data["median_telomeric_length_post_filtration_bp"], 5990)
                    self.assertEqual(data["censoring_rate_pct"], 50)
                    with (output / f"{name}_km_statistics.csv").open(newline="", encoding="utf-8") as handle:
                        row = next(csv.DictReader(handle))
                    self.assertAlmostEqual(float(row["km_censoring_rate_pct"]), 100 / 3)
                    self.assertEqual(row["km_status"], name)
                    if name == "reportable":
                        self.assertEqual(data["km_median_telomeric_length_bp"], 5000)
                        self.assertEqual(float(row["km_median_bp"]), 5000)
                    else:
                        for key in ("km_median_telomeric_length_bp", "km_median_95_ci_lower_bp", "km_median_95_ci_upper_bp"):
                            self.assertIsNone(data[key])
                        for key in ("km_median_bp", "km_ci_lower_bp", "km_ci_upper_bp"):
                            self.assertEqual(row[key], "")
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
