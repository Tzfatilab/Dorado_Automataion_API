import re
import sys
from html import escape

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QTextEdit,
    QMessageBox,
    QDialog,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from PySide6.QtCore import (
    Qt,
    QThread,
)

from PySide6.QtGui import QFont

from gui.ui_styles import apply_global_style
from workers.worker_thread import WorkerThread
from gui.sections.input_section import InputSection
from gui.sections.output_section import OutputSection
from gui.sections.config_section import ConfigSection
from gui.sections.workflow_section import WorkflowSection
from gui.sections.advanced_section import AdvancedSection
from gui.sections.sidebar_section import SidebarSection
from gui.sections.action_section import ActionSection

from core.validators import (
    inspect_bam_directory,
    validate_input_directories,
    validate_mode_inputs,
)
from core.workflow_constants import BASE_DIR


class AppWindow(
    QWidget,
    InputSection,
    OutputSection,
    ConfigSection,
    WorkflowSection,
    AdvancedSection,
    SidebarSection,
    ActionSection,
):
    """Main application window for pipeline configuration and execution."""

    def __init__(self):
        """Initialize the main window and construct the UI."""
        super().__init__()
        self.setWindowTitle("Telomere Analyzer")
        self.resize(700, 800)
        self.log_dialog = None
        self.worker = None
        self.worker_thread = None
        self.non_pod5_trim_status = "auto"
        self.bam_is_aligned = None
        self.bam_has_modifications = None
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        self.log.setLineWrapMode(QTextEdit.NoWrap)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        self._build_ui()

    def _build_ui(self):
        """
        Construct the main window layout using section mixins.

        Returns:
            None
        """
        main_layout = QHBoxLayout()

        sidebar = self._build_sidebar()
        sidebar.setObjectName("sidebar")

        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setSpacing(10)
        content_layout.setContentsMargins(12, 6, 12, 10)
        content_layout.setAlignment(Qt.AlignTop)

        content_layout.addWidget(self._build_section_header())

        content_layout.addSpacing(4)

        content_layout.addWidget(self._build_inputs())

        row = QHBoxLayout()
        row.setSpacing(12)

        row.addWidget(self._build_output(), 2)
        row.addWidget(self._build_config(), 1)

        content_layout.addLayout(row)

        content_layout.addWidget(self._build_workflow())

        content_layout.addWidget(self._build_advanced_options())

        content_layout.addLayout(self._build_buttons())

        main_layout.addWidget(sidebar, 0)
        main_layout.addWidget(content, 1)

        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setLayout(main_layout)

        apply_global_style(self)  

    def _show_error_dialog(self, title, errors):
        """
        Display a formatted list of validation errors.

        Args:
            title (str): Dialog title.
            errors (list[str]): List of error messages.

        Returns:
            None
        """
        QMessageBox.critical(self, title, "\n".join(errors))

    def _open_execution_log_dialog(self):
        """
        Create or show the execution log dialog.

        Returns:
            None
        """
        if self.log_dialog is None:
            self.log_dialog = QDialog(self)
            self.log_dialog.setWindowTitle("Execution Log")

            layout = QVBoxLayout()
            layout.addWidget(QLabel("Execution Log"))
            layout.addWidget(self.log)

            self.log_dialog.setLayout(layout)
            self.log_dialog.resize(860, 520)

        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def _append_log_line(self, text):
        """Append a visible log line and remember that the last line is not blank."""
        self.log.append(text)
        self._last_gui_log_blank = False

    def _append_log_blank(self):
        """Append one blank line, but never stack multiple blank lines."""
        if getattr(self, "_last_gui_log_blank", False):
            return
        self.log.append("")
        self._last_gui_log_blank = True

    def _append_log(self, message):
        """Append a worker log message to the execution log widget."""
        if message is None:
            return

        message = message.replace("\r\n", "\n").rstrip("\n")
        if message == "":
            return

        for raw_line in message.split("\n"):
            self._append_worker_log_line(raw_line)

    def _append_worker_log_line(self, line):
        """Normalize, filter, and render one worker log line."""
        line = self._prepare_log_line(line)
        if line is None:
            return

        r_detail = line.strip()
        if self._handle_nanotel_result_path(r_detail):
            return
        if self._consume_next_nanotel_result_path():
            return
        if self._handle_nanotel_state_line(r_detail):
            return
        if self._handle_nanotel_stats_line(r_detail):
            return
        if self._should_skip_log_detail(r_detail):
            return
        if self._handle_hidden_log_section(r_detail):
            return

        self._render_log_line(line)

    def _prepare_log_line(self, line):
        """Clean status glyphs and rewrite verbose NanoTel phrases."""
        line = line.translate(str.maketrans("", "", "\u2705\u274c\u2713\u2717\u25b6\u2715\u2022\u21b3"))
        for bad_status in ("ג“", "ג—"):
            line = line.replace(bad_status, "")
        line = re.sub(r"^(\s*)(OK|ERROR)\s+", r"\1", line)
        line = re.sub(r"^\s+(?=All .+ prerequisites validated$)", "", line)
        r_detail = line.strip()

        chunk_match = re.match(r"processing chunk\s+(\d+)", r_detail, re.IGNORECASE)
        if chunk_match:
            chunk_index = int(chunk_match.group(1))
            return f"NanoTel: chunk {chunk_index} complete"

        if (
            "The input argumetns for this run" in r_detail
            or "The input arguments for this run" in r_detail
        ):
            self._nanotel_actual_tvr_enabled = False
            return line.replace(r_detail, "NanoTel settings")
        if r_detail and set(r_detail) <= {"#"}:
            return None
        if r_detail.startswith("The patterns to search:"):
            return line.replace("The patterns to search:", "Telomere pattern:", 1)
        if r_detail.startswith("The sub-sequence length"):
            value = r_detail.split(":", 1)[1].strip() if ":" in r_detail else ""
            return f"Sub-sequence length: {value}"
        if r_detail.startswith("The minimal density for a telomeric subseq:"):
            return line.replace(
                "The minimal density for a telomeric subseq:",
                "Minimum telomere density:",
                1,
            )
        if r_detail.startswith("Additional Telomere variant repeats patterns were added:"):
            self._nanotel_actual_tvr_enabled = True
        return line

    def _handle_nanotel_result_path(self, r_detail):
        """Collapse NanoTel output file paths into one result-directory line."""
        if not (
            r_detail.startswith("NanoTel summary CSV saved to:")
            or r_detail.startswith("NanoTel read IDs saved to:")
        ):
            return False

        self._flush_pending_nanotel_stats_table()
        result_path = r_detail.split(":", 1)[1].strip()
        if not result_path:
            self._hide_next_nanotel_result_path = True
            return True

        result_dir = str(Path(result_path).parent)
        shown_dirs = getattr(self, "_shown_nanotel_result_dirs", set())
        if result_dir not in shown_dirs:
            shown_dirs.add(result_dir)
            self._shown_nanotel_result_dirs = shown_dirs
            self._append_timestamped_text(
                f"    Barcode results saved under: {result_dir}"
            )
        return True

    def _consume_next_nanotel_result_path(self):
        """Hide wrapped NanoTel result paths emitted on the following line."""
        if getattr(self, "_hide_next_nanotel_result_path", False):
            self._hide_next_nanotel_result_path = False
            return True
        return False

    def _handle_nanotel_state_line(self, r_detail):
        """Track NanoTel state while suppressing raw helper lines."""
        if r_detail == "The input files:":
            self._hide_next_nanotel_input_path = True
            return True
        if r_detail == "NanoTel analysis":
            self._nanotel_seen_barcode_processing = False
            return False
        if getattr(self, "_hide_next_nanotel_input_path", False):
            self._hide_next_nanotel_input_path = False
            return True
        if r_detail.startswith("Resolved barcode file prefix:"):
            self._nanotel_current_barcode = r_detail.split(":", 1)[1].strip()
            return False
        if re.match(r"^Processing barcode\d+", r_detail):
            if getattr(self, "_nanotel_seen_barcode_processing", False):
                self._append_log_blank()
            self._nanotel_seen_barcode_processing = True
        return False

    def _handle_nanotel_stats_line(self, r_detail):
        """Collect NanoTel stat-table lines and render one compact table."""
        tvr_title = "Telomere length with 1 mismatch allowed + tvr patterns.:"

        if r_detail == "Summary statistics of the sample reads length:":
            self._flush_pending_nanotel_stats_table()
            self._nanotel_stat_title = "Sample read length"
            self._nanotel_stat_tables = {}
            self._nanotel_pending_stats_render = False
            return True
        if r_detail == "Summary statistics for the Telomeric reads:":
            return True

        stat_titles = {
            "reads length:": "Telomeric read length",
            "Telomere length:": "Telomere length",
            "Telomere length with 1 mismatch allowed:": "Telomere length (1 mismatch)",
            tvr_title: "Telomere length (1 mismatch + TVR)",
        }
        if r_detail in stat_titles:
            self._nanotel_stat_title = stat_titles[r_detail]
            return True
        if getattr(self, "_nanotel_stat_title", None) and r_detail.startswith("Min."):
            self._nanotel_stat_values_pending = True
            return True
        if getattr(self, "_nanotel_stat_values_pending", False):
            self._nanotel_stat_values_pending = False
            self._store_nanotel_stat_values(r_detail.split())
            return True
        return False

    def _store_nanotel_stat_values(self, values):
        """Store one NanoTel stats row and render when the table is complete."""
        if len(values) != 6:
            return
        tables = getattr(self, "_nanotel_stat_tables", {})
        tables[self._nanotel_stat_title] = values
        self._nanotel_stat_tables = tables
        if self._nanotel_stat_title == "Telomere length (1 mismatch + TVR)":
            self._flush_pending_nanotel_stats_table()
        elif self._nanotel_stat_title == "Telomere length (1 mismatch)":
            if self._nanotel_tvr_is_enabled():
                self._nanotel_pending_stats_render = True
            else:
                self._flush_pending_nanotel_stats_table()
        self._nanotel_stat_title = None

    def _nanotel_tvr_is_enabled(self):
        """Return True when this NanoTel process confirmed TVR patterns."""
        return bool(getattr(self, "_nanotel_actual_tvr_enabled", False))

    def _flush_pending_nanotel_stats_table(self):
        """Render any collected NanoTel statistics once, then clear the buffer."""
        tables = getattr(self, "_nanotel_stat_tables", {})
        if not tables:
            self._nanotel_pending_stats_render = False
            return
        self._append_nanotel_stats_table(tables)
        self._nanotel_stat_tables = {}
        self._nanotel_pending_stats_render = False

    def _should_skip_log_detail(self, r_detail):
        """Skip duplicate or low-value details from verbose tools."""
        if r_detail.startswith("NanoTel completed for "):
            self._flush_pending_nanotel_stats_table()
        return (
            (
                r_detail.startswith("NanoTel completed for ")
                and " in " not in r_detail
            )
            or r_detail.endswith("R analysis completed")
            or r_detail.startswith("Post-analysis failed: Post-analysis failed:")
            or r_detail.startswith("Command completed in ")
            or r_detail.startswith("Work started at:")
        )

    def _handle_hidden_log_section(self, r_detail):
        """Hide workflow summaries and long R environment blocks."""
        if r_detail in {"WORKFLOW COMPLETED SUCCESSFULLY", "=== WORKFLOW SUMMARY ==="}:
            self._hide_workflow_summary = True
            return True
        if getattr(self, "_hide_workflow_summary", False):
            if (
                "PIPELINE COMPLETED SUCCESSFULLY" in r_detail
                or "PIPELINE FAILED" in r_detail
                or r_detail == "Pipeline finished successfully"
            ):
                self._hide_workflow_summary = False
                return False
            return True
        if r_detail.startswith("Log Path:"):
            self._hide_r_environment_details = True
            return True
        if getattr(self, "_hide_r_environment_details", False):
            if r_detail.startswith("Log Start Time:"):
                self._hide_r_environment_details = False
            return True
        return False

    def _append_timestamped_text(self, text):
        """Append escaped text with the standard GUI timestamp prefix."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_log_line(
            f'<span style="color: #777;">[{ts}]</span> '
            f'<span style="white-space: pre-wrap;">{escape(text)}</span>'
        )

    def _render_log_line(self, line):
        """Render one normalized log line with timestamp and emphasis."""
        if not line:
            self._append_log_blank()
            return

        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ', line):
            self._append_log_line(line)
            return

        ts = datetime.now().strftime("%H:%M:%S")
        is_stage_title = self._is_stage_title(line)
        is_key_update = self._is_key_update(line, is_stage_title)
        is_section_title = self._is_section_title(line, is_stage_title)
        is_major_milestone = self._is_major_milestone(line)
        status = self._line_status_prefix(line)

        leading = re.match(r"^\s*", line).group(0)
        body = line[len(leading):]
        text = escape(f"{leading}{status}{body}")
        if is_key_update:
            text = f"<b>{text}</b>"

        timestamp = f'<span style="color: #777;">[{ts}]</span> '
        if is_major_milestone:
            self._append_log_line('<span style="color: #999;">============================================================</span>')
        elif is_section_title and line not in {"Run started", "Setting up workflow"}:
            self._append_log_blank()

        self._append_log_line(f'{timestamp}<span style="white-space: pre-wrap;">{text}</span>')

        if is_major_milestone:
            self._append_log_line('<span style="color: #999;">============================================================</span>')
        elif is_section_title:
            self._append_log_line(f'{timestamp}<span style="color: #999;">========================</span>')

    @staticmethod
    def _is_stage_title(line):
        return line in {
            "Basecalling",
            "Demultiplexing",
            "BAM to FASTQ conversion",
            "NanoTel analysis",
            "Alignment",
            "Post-analysis",
        }

    @staticmethod
    def _is_key_update(line, is_stage_title):
        lower_line = line.lower()
        return (
            line == "Run started"
            or line.endswith(" workflow")
            or line == "Run details"
            or line.startswith("Step ")
            or is_stage_title
            or line.startswith("Command failed")
            or line.startswith("Basecalling:")
            or line.endswith(" completed.")
            or "pipeline completed" in lower_line
            or " failed" in lower_line
        )

    @staticmethod
    def _is_section_title(line, is_stage_title):
        return (
            line == "Run started"
            or line.endswith(" workflow")
            or line == "Run details"
            or line.startswith("Step ")
            or is_stage_title
        )

    @staticmethod
    def _is_major_milestone(line):
        lower_line = line.lower()
        return (
            line == "Run started"
            or line == "Pipeline finished successfully"
            or "pipeline completed" in lower_line
            or "pipeline failed" in lower_line
        )

    @staticmethod
    def _line_status_prefix(line):
        if line == "Pipeline finished successfully":
            return ""

        lower_line = line.lower()
        is_failure = (
            " failed" in lower_line
            or line.startswith("Required tool not found:")
            or line.startswith("Missing tools:")
            or " requires samtools or" in lower_line
        )
        is_success = (
            " completed" in lower_line
            or " completed successfully" in lower_line
        ) and not is_failure
        return "ERROR " if is_failure else "OK " if is_success else ""

    def _append_nanotel_stats_table(self, tables):
        """Render NanoTel read and telomere distributions in one compact table."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        content_indent = self.log.fontMetrics().horizontalAdvance(f"[{timestamp}]     ")
        headers = ("Min.", "1st Qu.", "Median", "Mean", "3rd Qu.", "Max.")
        table_order = (
            "Sample read length",
            "Telomeric read length",
            "Telomere length",
            "Telomere length (1 mismatch)",
            "Telomere length (1 mismatch + TVR)",
        )
        header_html = "".join(
            f'<th style="padding: 3px 7px; text-align: right; color: #555; '
            f'background: #f1f3f5; border: 1px solid #d7dce1;">{header}</th>'
            for header in headers
        )
        rows_html = ""
        for title in table_order:
            values = tables.get(title)
            if not values:
                continue
            value_html = "".join(
                f'<td style="padding: 3px 7px; text-align: right; '
                f'border: 1px solid #d7dce1;">{escape(value)}</td>'
                for value in values
            )
            rows_html += (
                '<tr>'
                f'<td style="padding: 3px 7px; border: 1px solid #d7dce1; '
                f'font-weight: 600;">{escape(title)}</td>{value_html}</tr>'
            )
        barcode = getattr(self, "_nanotel_current_barcode", "")
        title = "NanoTel analysis summary statistics"
        if barcode:
            title = f"{title} — {barcode}"
        if barcode:
            title = f"NanoTel analysis summary statistics for {barcode}"
        self._append_log_line(
            f'<span style="color: #777;">[{timestamp}]</span> '
            f'<span style="white-space: pre-wrap;">    {escape(title)}</span>'
        )
        self._append_log_blank()
        self._append_log_line(
            f'<table style="border-collapse: collapse; margin: 2px 0 5px {content_indent}px;">'
            '<tr><th style="padding: 3px 7px; text-align: left; color: #555; '
            'background: #f1f3f5; border: 1px solid #d7dce1;">Statistic</th>'
            f'{header_html}</tr>{rows_html}</table>'
        )
        self._append_log_blank()

    def _set_workflow_running(self, running):
        """
        Update button state while a workflow is active.

        Args:
            running (bool): True when workflow is running.

        Returns:
            None
        """
        self.run_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(True)

    def _is_workflow_running(self):
        """
        Check whether a background worker thread is active.

        Returns:
            bool: True when a workflow thread is running.
        """
        return self.worker_thread is not None and self.worker_thread.isRunning()

    def _build_worker(self, inputs, flags):
        """
        Create a WorkerThread configured from current UI selections.

        Args:
            inputs (dict): selected input paths.
            flags (dict): workflow step flags.

        Returns:
            WorkerThread: configured worker instance.
        """
        output_dir = self.output_input["edit"].text().strip()

        return WorkerThread(
            trial_name=Path(output_dir).name,
            pod5_path=inputs["pod5"],
            fastq_path=inputs["fastq"],
            bam_path=inputs["bam"],
            output_dir=output_dir,

            organism=self.organism.currentText().lower(),

            do_basecalling=flags["do_basecalling"],
            do_nanotel=flags["do_nanotel"],

            non_pod5_trim_status=self.non_pod5_trim_status,
            bam_is_aligned=self.bam_is_aligned,
            bam_has_modifications=self.bam_has_modifications,

            methylation_type=self._get_methylation_type(),
            chromosome_mapping=self.chromosome_mapping.isChecked(),
            nanotel_mapping=self.nanotel_mapping.isChecked(),
            summary_only=self.summary_only.isChecked(),

            tvr_mode=self.selected_tvr_mode,
            tvr_manual=self.tvr_manual.text().strip(),

            read_length=self.read_length.text().strip(),
            max_distance_edge=self.max_distance_edge.text().strip(),
            min_density_threshold=self.min_density_threshold.text().strip(),
        )

    def _prompt_non_pod5_trim_status(self, inputs, flags):
        """
        Prompt the user for trimming state when using FASTQ/BAM inputs.

        Args:
            inputs (dict): selected input paths.
            flags (dict): workflow flags.

        Returns:
            bool: True if workflow should continue, False if cancelled.
        """
        # Only relevant for FASTQ/BAM
        if self.selected_input == "pod5":
            self.non_pod5_trim_status = "auto"
            return True

        # If NanoTel not running → no need
        if not flags.get("do_nanotel", False):
            self.non_pod5_trim_status = "auto"
            return True

        # Ask user
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Input Trimming")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText("Were the reads trimmed for barcode removal?")
        dialog.setInformativeText("Used to adjust read length in filtering.")

        trimmed_btn   = dialog.addButton("Trimmed",   QMessageBox.AcceptRole)
        untrimmed_btn = dialog.addButton("Untrimmed", QMessageBox.AcceptRole)
        cancel_btn    = dialog.addButton("Cancel",    QMessageBox.RejectRole)

        dialog.exec()
        clicked = dialog.clickedButton()

        if clicked is cancel_btn:
            return False
        elif clicked is trimmed_btn:
            self.non_pod5_trim_status = "trimmed"
        elif clicked is untrimmed_btn:
            self.non_pod5_trim_status = "untrimmed"
        else:
            return False

        return True

    def _detect_bam_metadata(self, inputs, flags):
        """
        Detect BAM alignment and modification state.

        Trim state remains a separate prompt because it affects NanoTel
        filtering thresholds and cannot be proven reliably from a BAM file.
        """
        self.bam_is_aligned = None
        self.bam_has_modifications = None

        if not inputs.get("bam"):
            return True

        if not flags.get("do_nanotel", False):
            return True

        inspection = inspect_bam_directory(inputs["bam"])
        self.bam_is_aligned = inspection["is_aligned"]
        self.bam_has_modifications = inspection["has_modifications"]

        aligned_text = (
            "aligned" if self.bam_is_aligned is True
            else "not aligned" if self.bam_is_aligned is False
            else "alignment unknown"
        )
        modified_text = (
            "has modifications" if self.bam_has_modifications is True
            else "no modifications detected" if self.bam_has_modifications is False
            else "modification state unknown"
        )

        message = (
            f"BAM inspection: {inspection['bam_files']} BAM file(s), "
            f"{aligned_text}, {modified_text}."
        )
        if hasattr(self, "_append_log"):
            self._append_log(message)
            for error in inspection["errors"]:
                self._append_log(f"BAM inspection warning: {error}")

        return True

    def _start_workflow(self, inputs, flags):
        """
        Start the workflow worker in a separate thread.

        Args:
            inputs (dict): selected input paths.
            flags (dict): workflow step flags.

        Returns:
            None
        """
        if not hasattr(self, "log"):
            self.log = QTextEdit()

        self.log.clear()
        self._open_execution_log_dialog()
        self._set_workflow_running(True)

        self.worker_thread = QThread(self)
        self.worker = self._build_worker(inputs, flags)

        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.done.connect(self._on_workflow_done)

        # cleanup
        self.worker.done.connect(self.worker_thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._cleanup_worker)

        self.worker_thread.start()

    def _on_workflow_done(self, success, message):
        """
        Handle completion of the background workflow.

        Args:
            success (bool): True when workflow finished successfully.
            message (str): final status or error message.

        Returns:
            None
        """
        self._set_workflow_running(False)
        if message and not success:
            self._append_log(message)

    def _cleanup_worker(self):
        """
        Clear worker references after the background thread stops.

        Returns:
            None
        """
        self.worker = None
        self.worker_thread = None

    def _handle_cancel(self):
        """
        Cancel the currently running workflow or close the window.

        Returns:
            None
        """
        if self.worker is not None:
            self.worker.stop()
            return
        self.close()

    def show_log_dialog(self):
        """
        Validate the current selection and start workflow execution.

        Returns:
            None
        """
        if self._is_workflow_running():
            self._open_execution_log_dialog()
            return

        inputs = self._get_selected_inputs()

        output_dir = self.output_input["edit"].text().strip()
        if not output_dir:
            self._show_error_dialog("Invalid input", ["An output directory is required."])
            return

        errors = validate_mode_inputs(inputs=inputs,selected_workflows=self.selected_workflows)
        if errors:
            self._show_error_dialog("Invalid input", errors )
            return
        
        if not self.selected_workflows:
            self._show_error_dialog(
                "Workflow Required",
                ["Please select at least one analysis step."]
            )
            return
        
        flags = self._build_workflow_flags(inputs)
        if not self._prompt_non_pod5_trim_status(inputs, flags):
            return
        if not self._detect_bam_metadata(inputs, flags):
            return

        self._start_workflow(inputs, flags)


    def _get_selected_inputs(self):
        return {
            "pod5": self.input_path.text() if self.selected_input == "pod5" else "",
            "fastq": self.input_path.text() if self.selected_input == "fastq" else "",
            "bam": self.input_path.text() if self.selected_input == "bam" else "",
            "nanotel": "",
        }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())
