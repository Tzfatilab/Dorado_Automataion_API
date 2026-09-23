import re
import sys

from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QTextEdit, QMessageBox, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, QLayout

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
from gui.sections.execution_log_section import ExecutionLogSection

from core.validators import inspect_bam_directory, validate_mode_inputs


class AppWindow(
    QWidget,
    InputSection,
    OutputSection,
    ConfigSection,
    WorkflowSection,
    AdvancedSection,
    SidebarSection,
    ActionSection,
    ExecutionLogSection,
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
        self.log.setFont(QFont("Consolas", 9))
        self.log.setLineWrapMode(QTextEdit.NoWrap)
        self.progress_stage_label = QLabel("Workflow ·")
        self.progress_stage_label.setObjectName("progressStageLabel")
        self.progress_label = QLabel("Preparing workflow...")
        self.progress_label.setObjectName("progressLabel")
        self.progress_percent_label = QLabel("")
        self.progress_percent_label.setObjectName("progressPercentLabel")
        self.progress_percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("workflowProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        self._build_ui()

    @staticmethod
    def _screen_scale_factor(width, height):
        """Return a restrained UI scale for screens larger than 1600x900."""
        if width <= 0 or height <= 0:
            return 1.0
        size_ratio = min(width / 1600.0, height / 900.0)
        return round(max(1.0, min(1.20, 1.0 + (size_ratio - 1.0) * 0.40)), 2)

    @staticmethod
    def _scale_stylesheet(stylesheet, factor):
        """Scale pixel measurements in a Qt stylesheet."""
        if not stylesheet or factor == 1.0:
            return stylesheet

        def scaled_pixel(match):
            value = int(match.group(1))
            if value <= 1:
                return match.group(0)
            return f"{max(1, round(value * factor))}px"

        return re.sub(r"(?<![\w.])(\d+)px\b", scaled_pixel, stylesheet)

    def _apply_screen_scaling(self):
        """Enlarge the complete interface moderately on larger displays."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.ui_scale = 1.0
            return

        available = screen.availableGeometry()
        # A large monitor should not enlarge a restored/compact window. Base
        # scaling on the smaller of the screen and the actual window geometry.
        effective_width = min(available.width(), self.width())
        effective_height = min(available.height(), self.height())
        factor = self._screen_scale_factor(effective_width, effective_height)
        if available.width() >= 2200 or available.height() >= 1200:
            factor = max(1.15, factor)
        self.ui_scale = factor
        if factor == 1.0:
            return

        widgets = [self, *self.findChildren(QWidget)]
        for widget in widgets:
            stylesheet = widget.styleSheet()
            if stylesheet:
                widget.setStyleSheet(self._scale_stylesheet(stylesheet, factor))

            if widget.testAttribute(Qt.WA_SetFont):
                font = widget.font()
                if font.pixelSize() > 0:
                    font.setPixelSize(round(font.pixelSize() * factor))
                elif font.pointSizeF() > 0:
                    font.setPointSizeF(font.pointSizeF() * factor)
                widget.setFont(font)

            minimum = widget.minimumSize()
            maximum = widget.maximumSize()
            if minimum.width() == maximum.width() and maximum.width() < 16777215:
                widget.setFixedWidth(round(maximum.width() * factor))
            if minimum.height() == maximum.height() and maximum.height() < 16777215:
                widget.setFixedHeight(round(maximum.height() * factor))

        for layout in self.findChildren(QLayout):
            margins = layout.contentsMargins()
            layout.setContentsMargins(
                round(margins.left() * factor),
                round(margins.top() * factor),
                round(margins.right() * factor),
                round(margins.bottom() * factor),
            )
            if layout.spacing() >= 0:
                layout.setSpacing(round(layout.spacing() * factor))

    def resizeEvent(self, event):
        """Adapt long option text when the application window is resized."""
        super().resizeEvent(event)
        self._update_chromosome_mapping_text()

    def _update_chromosome_mapping_text(self):
        """Keep the shortened chromosome-mapping label consistent."""
        checkbox = getattr(self, "chromosome_mapping", None)
        if checkbox is None:
            return

        label_text = "Align reads to genome"
        if checkbox.text() != label_text:
            checkbox.setText(label_text)
            checkbox.updateGeometry()

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
            allow_mismatch=self.allow_mismatch.isChecked(),

            read_length=self.read_length.text().strip(),
            max_distance_edge=self.max_distance_edge.text().strip(),
            max_telomere_start=self.max_telomere_start.text().strip(),
            min_density_threshold=self.min_density_threshold.text().strip(),
            short_telomere_threshold=self.short_telomere_threshold.text().strip(),
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
        # Preserve the mode used by this run for its final summary display.
        self._nanotel_allow_mismatch = self.allow_mismatch.isChecked()
        self._show_busy_progress("Preparing workflow…")
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
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        self.progress_percent_label.setText("100%" if success else "Stopped")
        self.progress_stage_label.setText("Workflow ·")
        self.progress_label.setText(
            "Workflow completed" if success else "Workflow stopped before completion"
        )
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
