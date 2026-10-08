"""Test the real command/notification/renderer methods without starting a GUI."""
import ast
from html import escape
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from dorado_workflow.processors.nanotel import NanoTelProcessor

ROOT = Path(__file__).resolve().parents[1]
# Execute the actual rendering/routing methods; Qt installation isn't required
# for these data/markup checks. A full GUI smoke test remains separate.
tree = ast.parse((ROOT / "dorado_gui/gui/sections/execution_log_section.py").read_text(encoding="utf-8"))
section = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ExecutionLogSection")
section.body = [node for node in section.body if isinstance(node, ast.FunctionDef)
                and node.name in ("_handle_nanotel_analysis_result", "_append_worker_log_line")]
namespace = dict(json=json, Path=Path, escape=escape, re=re)
exec(compile(ast.Module(body=[section], type_ignores=[]), "actual_log_methods", "exec"), namespace)


class LogHarness(namespace["ExecutionLogSection"]):
    def __init__(self):
        self.events = []

    def _flush_pending_nanotel_stats_table(self):
        self.events.append("descriptive table flushed")

    def _append_timestamped_text(self, text):
        self.events.append(text)

    def _append_log_line(self, text):
        self.events.append(text)

    def _append_log_blank(self):
        self.events.append("")

    def _prepare_log_line(self, line):
        return line


class GUIAnalysisIntegrationTests(unittest.TestCase):
    def test_command_full_run_only(self):
        processor = NanoTelProcessor.__new__(NanoTelProcessor)
        config = Mock()
        config.get_nanotel_script_path.return_value = str(ROOT / "dorado_workflow/data/NanoTel.R")
        processor.context = SimpleNamespace(config_manager=config, path_manager=Mock())
        processor.context.path_manager.get_logs_dir_path.return_value = ROOT / "logs with spaces"
        task = dict(barcode="barcode01", input_dir=ROOT / "input with spaces", output_dir=ROOT / "output with spaces")
        for summary_only in (False, True):
            config.get_nanotel_params.return_value = dict(summary_only=summary_only)
            command = processor._build_command(task)
            self.assertEqual("--analysis" in command, not summary_only)
            self.assertEqual("--summary_only" in command, summary_only)

    def test_notifications_fresh_success_only(self):
        with tempfile.TemporaryDirectory(prefix="KM integration ") as directory:
            root = Path(directory)
            path = root / "barcode01_analysis.json"
            task = dict(barcode="barcode01", output_dir=root, fastq_count=1)
            processor = NanoTelProcessor.__new__(NanoTelProcessor)
            processor.context = SimpleNamespace(logger=Mock(), command_executor=Mock(), barcode_manager=Mock())
            processor._build_command = Mock(return_value="command")
            processor._last_command_duration = Mock(return_value=None)
            for case in ("new", "stale", "failed"):
                processor.context.logger.reset_mock()
                def execute(*args, **kwargs):
                    if case != "stale":
                        before = path.stat().st_mtime_ns if path.exists() else 0
                        path.write_text("{}", encoding="utf-8")
                        stamp = max(before + 1000000000, path.stat().st_mtime_ns)
                        os.utime(path, ns=(stamp, stamp))
                    if case == "failed":
                        raise RuntimeError("fixture failed after write")
                processor.context.command_executor.execute.side_effect = execute
                results = processor._process_barcodes_sequential([task])
                notifications = [call.args[0] for call in processor.context.logger.info.call_args_list
                                 if call.args[0].startswith("NanoTel analysis JSON saved to:")]
                self.assertEqual(len(notifications), 1 if case == "new" else 0)
                self.assertEqual(results["barcode01"], case != "failed")

    def test_all_reporting_cases_and_escaped_reasons(self):
        with tempfile.TemporaryDirectory(prefix="KM reports ") as directory:
            path = Path(directory) / "barcode01_analysis.json"
            for status in ("reportable", "too_wide", "non_estimable", "invalid", "failed"):
                reported = status == "reportable"
                result = dict(barcode="barcode01",
                    km_median_telomeric_length_bp=5000 if reported else None,
                    km_median_95_ci_lower_bp=4500 if reported else None,
                    km_median_95_ci_upper_bp=5500 if reported else None,
                    km_whole_relative_ci_width_pct=20 if reported else 24 if status == "too_wide" else None,
                    km_reporting_reason=None if reported else "Reason <script> & unrounded width exceeds limit",
                    censoring_rate_pct=50, km_censoring_rate_pct=33.3)
                path.write_text(json.dumps(result), encoding="utf-8")
                harness = LogHarness()
                harness._append_worker_log_line(f"NanoTel analysis JSON saved to: {path}")
                markup = "\n".join(harness.events)
                self.assertEqual(harness.events[0], "descriptive table flushed")
                self.assertIn("<table", markup)
                self.assertNotIn("censor", markup.lower())
                if reported:
                    self.assertIn("5,000 bp", markup)
                    self.assertIn("4,500-5,500 bp", markup)
                    self.assertIn("20.0%", markup)
                else:
                    self.assertIn("Not reported", markup)
                    self.assertNotIn("5,000", markup)
                    self.assertIn("&lt;script&gt; &amp;", markup)
                    self.assertIn("unrounded width exceeds limit", markup)
                    self.assertIn("24.0%" if status == "too_wide" else "Not available", markup)

    def test_missing_and_malformed_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            for content in (None, "broken", "[]", "{}"):
                if content is not None:
                    path.write_text(content, encoding="utf-8")
                harness = LogHarness()
                self.assertTrue(harness._handle_nanotel_analysis_result(f"NanoTel analysis JSON saved to: {path}"))
                self.assertIn("could not be read", "\n".join(harness.events))
                self.assertNotIn("<table", "\n".join(harness.events))
