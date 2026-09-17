"""Run with unittest; set RSCRIPT when Rscript is not on PATH."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from dorado_workflow.processors.nanotel import NanoTelProcessor

ROOT = Path(__file__).resolve().parents[1]


class KMReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rscript = os.environ.get("RSCRIPT") or shutil.which("Rscript")
        if not rscript:
            raise unittest.SkipTest("Rscript required; set RSCRIPT")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.output = Path(cls.temp.name)
        result = subprocess.run(
            [rscript, "--vanilla", str(ROOT / "tests/km_reporting_checks.R"),
             str(ROOT / "dorado_workflow/data/NanoTel.R"), str(cls.output)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.processor = NanoTelProcessor.__new__(NanoTelProcessor)

    def parse(self, name):
        return self.processor._parse_barcode_results_file(name, self.output / f"{name}_results.txt")

    def test_r_checks_and_reportable_output(self):
        row = self.parse("reportable")
        self.assertEqual(row["KM Median Telomeric Length"], "5,000 bp")
        self.assertEqual(row["KM Median 95% Confidence Interval"], "4,500–5,500 bp")
        self.assertEqual(row["KM Whole Relative CI Width"], "20.0%")

    def test_withholding_survives_combined_export(self):
        for name in ("too_wide", "non_estimable", "failed"):
            with self.subTest(name=name):
                row = self.parse(name)
                table = "\n".join(self.processor._format_combined_results_table([row]))
                self.assertIn("Not reported", table)
                self.assertIn(row["KM Reporting Reason"], table)
                for hidden in ("5,000", "4,400", "5,600", "5,500"):
                    self.assertNotIn(hidden, table)
                self.assertEqual(row["Median Telomeric Length (post-filtration)"], "5,990 bp")

    def test_legacy_and_mixed_reports(self):
        source = (self.output / "reportable_results.txt").read_text(encoding="utf-8")
        old = "\n".join(line for line in source.splitlines() if not line.startswith("KM "))
        for name, text in (("old", old), ("legacy", old + "\nKM Median : 9,999 bp")):
            (self.output / f"{name}_results.txt").write_text(text, encoding="utf-8")
        old_row = self.parse("old")
        self.assertNotIn("KM Median Telomeric Length", old_row)
        legacy = self.parse("legacy")
        self.assertEqual(legacy["KM Median Telomeric Length"], "Not reported")
        table = "\n".join(self.processor._format_combined_results_table(
            [old_row, legacy, self.parse("reportable"), self.parse("too_wide")]))
        self.assertNotIn("9,999", table)
        self.assertIn("Not available", table)
        self.assertIn("4,500–5,500 bp", table)


if __name__ == "__main__":
    unittest.main()
