import re
import sys

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

from core.validators import validate_input_directories, validate_mode_inputs
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

    def _append_log(self, message):
        """
        Append a log message to the execution log widget.

        Args:
            message (str | None): Text emitted by the worker thread.

        Returns:
            None
        """
        if message is None:
            return

        message = message.replace("\r\n", "\n").rstrip("\n")
        if message == "":
            return

        for line in message.split("\n"):
            if not line:
                self.log.append("")
            elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ', line):
                self.log.append(line)
            else:
                ts = datetime.now().strftime("%H:%M:%S")
                self.log.append(f"[{ts}] {line}")

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

            methylation_type=self._get_methylation_type(),
            chromosome_mapping=self.chromosome_mapping.isChecked(),

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
        if message:
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
