"""Execution-log rendering and progress display for the main window.

The host supplies the log widget and progress labels. Workflow execution stays
in AppWindow; this section only interprets and presents its messages.
"""
import re
from datetime import datetime
from html import escape
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget


class ExecutionLogSection:
    """Keep message formatting, NanoTel summaries and progress state together."""

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
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)
            layout.addWidget(self.log)

            progress_panel = QWidget()
            progress_panel.setObjectName("progressPanel")
            progress_layout = QVBoxLayout(progress_panel)
            progress_layout.setContentsMargins(8, 6, 8, 7)
            progress_layout.setSpacing(3)
            detail_row = QHBoxLayout()
            detail_row.setSpacing(5)
            detail_row.addWidget(self.progress_stage_label)
            detail_row.addWidget(self.progress_label, 1)
            detail_row.addWidget(self.progress_percent_label)
            progress_layout.addLayout(detail_row)
            progress_layout.addWidget(self.progress_bar)
            layout.addWidget(progress_panel)

            self.log_dialog.setLayout(layout)
            self.log_dialog.resize(700, 420)

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
            self._update_progress_from_log(raw_line.strip())
            self._append_worker_log_line(raw_line)

    def _update_progress_from_log(self, line):
        """Keep the progress panel moving from the worker's streamed messages."""
        if not line:
            return

        barcode_match = re.match(r"Processing\s+(barcode\d+)", line, re.IGNORECASE)
        if barcode_match:
            self._nanotel_current_barcode = barcode_match.group(1)
            self.progress_stage_label.setText("NanoTel analysis ·")
            self._show_busy_progress(f"Processing {self._nanotel_current_barcode} · starting...")
            return

        # Accept both NanoTel's current output and a total-aware form, so the GUI
        # becomes determinate automatically if the backend reports "of N".
        chunk_match = re.search(
            r"(?:processing\s+chunk|NanoTel:\s*chunk)\s+(\d+)"
            r"(?:\s+of\s+(\d+))?",
            line,
            re.IGNORECASE,
        )
        if chunk_match:
            chunk = int(chunk_match.group(1))
            total = int(chunk_match.group(2)) if chunk_match.group(2) else None
            barcode = getattr(self, "_nanotel_current_barcode", "sample")
            if total and total > 0:
                percent = min(100, round(chunk * 100 / total))
                self.progress_bar.setRange(0, 100)
                if chunk >= total:
                    # Reading the final chunk does not mean NanoTel has finished:
                    # it still combines results, calculates statistics, and writes files.
                    # Reserve 100% for the worker's real completion signal.
                    self.progress_bar.setValue(95)
                    self.progress_label.setText(f"Processing {barcode}")
                    self.progress_percent_label.setText("")
                else:
                    self.progress_bar.setValue(percent)
                    self.progress_label.setText(f"Processing {barcode}")
                    self.progress_percent_label.setText(f"{percent}%")
            else:
                self._show_busy_progress(f"Processing {barcode}")
            return

        if line.strip().startswith("NanoTel completed for "):
            self._show_busy_progress("NanoTel complete · continuing workflow...")
            return

        stage = line.strip()
        if stage in {
            "Basecalling", "Demultiplexing", "BAM to FASTQ conversion",
            "NanoTel analysis", "Alignment", "Post-analysis",
        }:
            self.progress_stage_label.setText(f"{stage} ·")
            self._show_busy_progress("Running...")

    def _show_busy_progress(self, text):
        """Show Qt's animated indeterminate bar for work with no known total."""
        self.progress_label.setText(text)
        self.progress_percent_label.setText("")
        self.progress_bar.setRange(0, 0)

    def _append_worker_log_line(self, line):
        """Normalize, filter, and render one worker log line."""
        line = self._prepare_log_line(line)
        if line is None:
            return

        analysis_line = line.strip()
        if re.match(r"^NanoTel:\s*chunk\s+\d+", analysis_line, re.IGNORECASE):
            return
        if self._handle_nanotel_result_path(analysis_line):
            return
        if self._consume_next_nanotel_result_path():
            return
        if self._handle_nanotel_state_line(analysis_line):
            return
        if self._handle_nanotel_stats_line(analysis_line):
            return
        if self._should_skip_log_detail(analysis_line):
            return
        if self._handle_hidden_log_section(analysis_line):
            return

        self._render_log_line(line)

    def _prepare_log_line(self, line):
        """Clean status glyphs and rewrite verbose NanoTel phrases."""
        line = line.translate(str.maketrans("", "", "\u2705\u274c\u2713\u2717\u25b6\u2715\u2022\u21b3"))
        for bad_status in ("ג“", "ג—"):
            line = line.replace(bad_status, "")
        line = re.sub(r"^(\s*)(OK|ERROR)\s+", r"\1", line)
        line = re.sub(r"^\s+(?=All .+ prerequisites validated$)", "", line)
        analysis_line = line.strip()

        chunk_match = re.match(r"processing chunk\s+(\d+)", analysis_line, re.IGNORECASE)
        if chunk_match:
            chunk_index = int(chunk_match.group(1))
            return f"NanoTel: chunk {chunk_index} complete"

        if (
            "The input argumetns for this run" in analysis_line
            or "The input arguments for this run" in analysis_line
        ):
            self._nanotel_actual_tvr_enabled = False
            return line.replace(analysis_line, "NanoTel settings")
        if analysis_line and set(analysis_line) <= {"#"}:
            return None
        if analysis_line.startswith("The patterns to search:"):
            return line.replace("The patterns to search:", "Telomere pattern:", 1)
        if analysis_line.startswith("The sub-sequence length"):
            value = analysis_line.split(":", 1)[1].strip() if ":" in analysis_line else ""
            return f"Sub-sequence length: {value}"
        if analysis_line.startswith("The minimal density for a telomeric subseq:"):
            return line.replace(
                "The minimal density for a telomeric subseq:",
                "Minimum telomere density:",
                1,
            )
        if analysis_line.startswith("Additional Telomere variant repeats patterns were added:"):
            self._nanotel_actual_tvr_enabled = True
        return line

    def _handle_nanotel_result_path(self, analysis_line):
        """Collapse NanoTel output file paths into one result-directory line."""
        if not (
            analysis_line.startswith("NanoTel summary CSV saved to:")
            or analysis_line.startswith("NanoTel read IDs saved to:")
        ):
            return False

        self._flush_pending_nanotel_stats_table()
        result_path = analysis_line.split(":", 1)[1].strip()
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

    def _handle_nanotel_state_line(self, analysis_line):
        """Track NanoTel state while suppressing raw helper lines."""
        if analysis_line == "The input files:":
            self._hide_next_nanotel_input_path = True
            return True
        if analysis_line == "NanoTel analysis":
            self._nanotel_seen_barcode_processing = False
            return False
        if getattr(self, "_hide_next_nanotel_input_path", False):
            self._hide_next_nanotel_input_path = False
            return True
        if analysis_line.startswith("Resolved barcode file prefix:"):
            self._nanotel_current_barcode = analysis_line.split(":", 1)[1].strip()
            return False
        if re.match(r"^Processing barcode\d+", analysis_line):
            if getattr(self, "_nanotel_seen_barcode_processing", False):
                self._append_log_blank()
            self._nanotel_seen_barcode_processing = True
        return False

    def _handle_nanotel_stats_line(self, analysis_line):
        """Collect NanoTel stat-table lines and render one compact table."""
        tvr_title = "Telomere length with 1 mismatch allowed + tvr patterns.:"

        if analysis_line == "Summary statistics of the sample reads length:":
            self._flush_pending_nanotel_stats_table()
            self._nanotel_stat_title = "Sample read length"
            self._nanotel_stat_tables = {}
            self._nanotel_pending_stats_render = False
            return True
        if analysis_line == "Summary statistics for the Telomeric reads:":
            return True

        stat_titles = {
            "reads length:": "Telomeric read length",
            "Telomere length:": "Telomere length",
            "Telomere length with 1 mismatch allowed:": "Telomere length (1 mismatch)",
            tvr_title: "Telomere length (1 mismatch + TVR)",
        }
        if analysis_line in stat_titles:
            self._nanotel_stat_title = stat_titles[analysis_line]
            return True
        if getattr(self, "_nanotel_stat_title", None) and analysis_line.startswith("Min."):
            self._nanotel_stat_values_pending = True
            return True
        if getattr(self, "_nanotel_stat_values_pending", False):
            self._nanotel_stat_values_pending = False
            self._store_nanotel_stat_values(analysis_line.split())
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

    def _should_skip_log_detail(self, analysis_line):
        """Skip duplicate or low-value details from verbose tools."""
        if analysis_line.startswith("NanoTel completed for "):
            self._flush_pending_nanotel_stats_table()
        return (
            (
                analysis_line.startswith("NanoTel completed for ")
                and " in " not in analysis_line
            )
            or analysis_line.endswith("R analysis completed")
            or analysis_line.startswith("Post-analysis failed: Post-analysis failed:")
            or analysis_line.startswith("Command completed in ")
            or analysis_line.startswith("Work started at:")
        )

    def _handle_hidden_log_section(self, analysis_line):
        """Hide workflow summaries and long R environment blocks."""
        if analysis_line in {"WORKFLOW COMPLETED SUCCESSFULLY", "=== WORKFLOW SUMMARY ==="}:
            self._hide_workflow_summary = True
            return True
        if getattr(self, "_hide_workflow_summary", False):
            if (
                "PIPELINE COMPLETED SUCCESSFULLY" in analysis_line
                or "PIPELINE FAILED" in analysis_line
                or analysis_line == "Pipeline finished successfully"
            ):
                self._hide_workflow_summary = False
                return False
            return True
        if analysis_line.startswith("Log Path:"):
            self._hide_r_environment_details = True
            return True
        if getattr(self, "_hide_r_environment_details", False):
            if analysis_line.startswith("Log Start Time:"):
                self._hide_r_environment_details = False
            return True
        return False

    def _append_timestamped_text(self, text):
        """Append escaped text with the standard GUI timestamp prefix."""
        timestamp_text = datetime.now().strftime("%H:%M:%S")
        self._append_log_line(
            f'<span style="color: #777;">[{timestamp_text}]</span> '
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

        timestamp_text = datetime.now().strftime("%H:%M:%S")
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

        timestamp = f'<span style="color: #777;">[{timestamp_text}]</span> '
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
        allow_mismatch = bool(
            getattr(self, "_nanotel_allow_mismatch", False)
        )
        header_html = "".join(
            f'<th style="padding: 3px 7px; text-align: right; color: #555; '
            f'background: #f1f3f5; border: 1px solid #d7dce1;">{header}</th>'
            for header in headers
        )
        rows_html = ""
        for title in table_order:
            # When "Allow 1 mismatch" is off, do not show mismatch results.
            # Show the TVR result with an exact-match label instead.
            if not allow_mismatch and title == "Telomere length (1 mismatch)":
                continue
            values = tables.get(title)
            if not values:
                continue
            display_title = title
            if (
                not allow_mismatch
                and title == "Telomere length (1 mismatch + TVR)"
            ):
                display_title = "Telomere length (+ TVR)"
            value_html = "".join(
                f'<td style="padding: 3px 7px; text-align: right; '
                f'border: 1px solid #d7dce1;">{escape(value)}</td>'
                for value in values
            )
            rows_html += (
                '<tr>'
                f'<td style="padding: 3px 7px; border: 1px solid #d7dce1; '
                f'font-weight: 600;">{escape(display_title)}</td>{value_html}</tr>'
            )
        barcode = getattr(self, "_nanotel_current_barcode", "")
        title = "NanoTel analysis summary statistics"
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

