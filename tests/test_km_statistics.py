"""Run-level exports use assessed rows and equal barcode weights."""
import csv
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from dorado_workflow.reports.km_statistics import KM_FIELDS, write_km_run_statistics
from dorado_workflow.processors.nanotel import NanoTelProcessor


class KMStatisticsTests(unittest.TestCase):
    def write_source(self, directory, barcode, status, rate):
        path = directory / f"{barcode}_km_statistics.csv"
        row = dict.fromkeys(KM_FIELDS, "")
        row.update(barcode=barcode, km_status=status, km_censoring_rate_pct=rate,
                   km_median_bp=5000, km_ci_lower_bp=4500, km_ci_upper_bp=5500)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=KM_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_mean_withholding_and_explicit_run_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.write_source(root, "barcode01", "reportable", 10)
            second = self.write_source(root, "barcode02", "too_wide", 30)
            third = self.write_source(root, "barcode03", "failed", "")
            self.write_source(root, "old_barcode", "reportable", 100)
            summary = write_km_run_statistics([first, second, third], root)
            self.assertEqual(summary["mean_barcode_km_censoring_rate_pct"], 20)
            self.assertEqual(summary["barcodes_with_reportable_km"], 1)
            self.assertEqual(summary["barcodes_with_withheld_km"], 2)
            self.assertEqual(summary["barcodes_with_available_km_censoring"], 2)
            with (root / "km_barcode_statistics.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["km_median_bp"], "5000")
            self.assertEqual(rows[1]["km_median_bp"], "")
            self.assertEqual(rows[2]["km_ci_upper_bp"], "")
            write_km_run_statistics([], root)
            with (root / "km_run_statistics.csv").open(newline="") as handle:
                empty = next(csv.DictReader(handle))
            self.assertEqual(empty["mean_barcode_km_censoring_rate_pct"], "")
            self.assertEqual(empty["barcodes_with_reportable_km"], "0")

    def test_duplicate_and_invalid_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root, "barcode01", "reportable", 10)
            with self.assertRaises(ValueError):
                write_km_run_statistics([source, source], root)
            for rate in ("nan", "inf", "-1", "101"):
                source = self.write_source(root, "barcode01", "reportable", rate)
                with self.subTest(rate=rate), self.assertRaises(ValueError):
                    write_km_run_statistics([source], root)

    def test_processor_collects_only_current_successful_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = []
            for barcode in ("barcode01", "barcode02", "barcode03"):
                folder = root / barcode
                folder.mkdir()
                self.write_source(folder, barcode, "reportable", 10)
                tasks.append({"barcode": barcode, "output_dir": folder})
            processor = NanoTelProcessor.__new__(NanoTelProcessor)
            processor.output_dir = root
            processor.context = SimpleNamespace(logger=Mock())
            processor.log_start = Mock()
            processor.log_complete = Mock()
            processor.validate_inputs = Mock(return_value=True)
            processor._create_barcode_tasks = Mock(return_value=tasks)
            processor._collect_statistics = Mock(return_value={})

            def process(_):
                # Successful barcode01 writes a current export; barcode02's old
                # export is unchanged. barcode03 writes but its command fails.
                for task in (tasks[0], tasks[2]):
                    path = task["output_dir"] / f"{task['barcode']}_km_statistics.csv"
                    stamp = path.stat().st_mtime_ns + 1000000000
                    os.utime(path, ns=(stamp, stamp))
                return {"barcode01": True, "barcode02": True, "barcode03": False}

            processor._process_barcodes_sequential = process
            result = processor.execute("unused")
            self.assertFalse(result.success) # The failed barcode is still reported.
            with (root / "km_barcode_statistics.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["barcode"] for row in rows], ["barcode01"])
            processor._process_barcodes_sequential = Mock(return_value={
                "barcode01": True, "barcode02": True, "barcode03": True,
            })
            self.assertTrue(processor.execute("unused").success)
            with (root / "km_barcode_statistics.csv").open(newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])


if __name__ == "__main__":
    unittest.main()
