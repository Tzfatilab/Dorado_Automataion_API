from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
)

from PySide6.QtGui import QIcon
from gui.ui_styles import make_card, make_help_button
from gui.widgets.selection_widgets import SelectCard, SelectionGrid
from core.workflow_constants import BASE_DIR


class InputSection:
    """
    Mixin providing the input-selection card used by the main window.

    Responsibilities:
    - Build the Input Data card (selection cards + input path row)
    - Provide helpers for browsing and creating folder buttons
    - Expose get_selected_inputs() for other components to query UI state
    """

    def _build_inputs(self):
        """Construct the Input Data card containing selection cards and path row.

        Returns:
            QWidget: a styled card widget (from make_card) containing the input UI.

        Inputs:
            None; uses instance state.
        """
        self.selected_input = "pod5"
        self.cards = {}
        
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Select input directory...")

        box = make_card("Input Data")
        layout = QVBoxLayout(box)
        layout.setSpacing(16)

        subtitle = QLabel("Select your input data type")
        subtitle.setStyleSheet("color: #6b7280; font-size: 14px; background-color: white;")
        layout.addWidget(subtitle)
        make_help_button(
            box, "Input Data",
            "<h2 style='color:#1d4ed8'>Choose your input</h2>"
            "<p>Select the file type you already have, then choose its folder.</p>"
            "<h3>POD5 · raw signals</h3>"
            "<p>Choose <b>Basecalling</b> to convert raw signals to BAM reads. "
            "The workflow then separates barcodes and produces FASTQ files.</p>"
            "<h3>BAM · basecalled reads</h3>"
            "<p>Basecalling is skipped. BAM reads are converted to FASTQ "
            "for NanoTel analysis.</p>"
            "<h3>FASTQ · sequence reads</h3>"
            "<p>Barcode folders are used directly. If the reads have not been "
            "split by barcode, Dorado demultiplexes them first using the "
            "configured kit.</p>"
            "<h3>Existing project</h3>"
            "<p>Choose the original project or results folder. Recalculate results reads the original "
            "before-filter NanoTel tables from CSV or the source worksheets in Excel. Mapping also needs "
            "saved aligned BAMs or FASTQ reads. The original project is not overwritten.</p>"
            "<hr><p>Results are saved in the <b>Output Path</b> selected below.</p>",
            subtitle
        )

        row = SelectionGrid(4, spacing=20, minimum_card_width=260)

        for key, label, desc in [
            ("pod5", "POD5 (Raw Signals)", "Start from raw POD5 signals."),
            ("bam", "BAM (Basecalled)", "Analyze basecalled BAM reads."),
            ("fastq", "FASTQ", "Use existing FASTQ files."),
            ("project", "Existing project", "Recalculate saved results."),
        ]:
            card = SelectCard(key, label, desc, theme="blue")
            card.mousePressEvent = lambda e, k=key: self._select_input(k)
            self.cards[key] = card
            row.add_card(card)

        layout.addWidget(row)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        label = QLabel("Input Path")
        label.setFixedWidth(80)
        label.setStyleSheet("font-weight: 700; color: #374151;")
        label.setAlignment(Qt.AlignCenter)

        button = self._create_folder_button(self._browse_input)

        path_row.addWidget(label)
        path_row.addWidget(self.input_path)
        path_row.addWidget(button)

        layout.addLayout(path_row)
        self._select_input("pod5")
        self.input_path.editingFinished.connect(self._load_post_analysis_source)

        return box

    def _select_input(self, key):
        """Mark the given input card as selected and update visuals.

        Args:
            key (str): one of "pod5", "bam", "fastq".

        Returns:
            None.
        """
        self.selected_input = key
        if key != "project":
            self._post_loaded_path = None
        for k, card in self.cards.items():
            card.set_selected(k == key)
        if hasattr(self, "workflow_cards"):
            if key == "project":
                self.selected_workflows = {"post_analysis"}
            else:
                self.selected_workflows.discard("post_analysis")
            for name, card in self.workflow_cards.items():
                card.set_selected(name in self.selected_workflows)
            if hasattr(self, "nanotel_options_card"):
                self._update_advanced_options_state()
        self.input_path.setPlaceholderText("Select the original project folder..." if key == "project" else "Select input directory...")


    def _browse_input(self, edit=None):
        """Open a directory picker and place the chosen path into the provided QLineEdit.

        Args:
            edit (QLineEdit|None): widget to fill; if None uses self.input_path.

        Returns:
            None.
        """
        if edit is None:
            edit = self.input_path
        path = QFileDialog.getExistingDirectory(self, "Select input", edit.text())
        if path:
            edit.setText(path)
            self._load_post_analysis_source()

    def get_selected_inputs(self):
        """Return the selected input paths according to the current UI selection.

        Returns:
            dict: keys: 'pod5', 'fastq', 'bam', 'nanotel' with path strings (empty if not selected).

        Inputs:
            None; uses instance state.
        """
        return {
            "pod5": self.input_path.text() if self.selected_input == "pod5" else "",
            "fastq": self.input_path.text() if self.selected_input == "fastq" else "",
            "bam": self.input_path.text() if self.selected_input == "bam" else "",
            "nanotel": "",
            "project": self.input_path.text() if self.selected_input == "project" else "",
        }
    
    def _create_folder_button(self, callback):
        """
        Create a standardized folder-browse QPushButton.

        Args:
            callback (callable): function to call when button is clicked.

        Returns:
            QPushButton: configured button with folder icon and styles.
        """
        btn = QPushButton()

        btn.setIcon(
            QIcon(str(BASE_DIR / "icons" / "folder.png"))
        )

        btn.setFixedSize(40,40)
        btn.setIconSize(QSize(55, 55))
        btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
            }

            QPushButton:hover {
                border: 1px solid #2563EB;
                background-color: #F9FAFB;
            }

            QPushButton:pressed {
                background-color: #F3F4F6;
                border: 1px solid #2563EB;
            }
        """)

        btn.clicked.connect(lambda: callback())
        return btn

    def _load_post_analysis_source(self):
        """Preview original detection settings without editing the project.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
        if self.selected_input != "project" or not hasattr(self, "nanotel_mapping"):
            return
        path = self.input_path.text().strip()
        if not path or path == getattr(self, "_post_loaded_path", None):
            return
        try:
            from dorado_workflow.processors.project_sources import ProjectSources
            source = ProjectSources.inspect(path)
            self._post_loaded_path = path
            self.summary_only.setChecked(bool(source.params.get("summary_only", False)))
            self._post_source_organism = source.organism
            self.nanotel_mapping.setChecked(bool(source.settings.get("run_mapping_analysis", False)))
            self.organism.setEnabled(not bool(source.organism))
            self.allow_mismatch.setChecked(source.params.get("max_mismatch") == 1)
            if source.organism:
                index = self.organism.findText(source.organism, Qt.MatchFixedString)
                if index >= 0: self.organism.setCurrentIndex(index)
            params = source.params
            for name, key in (("read_length", "min_read_length"), ("max_telomere_start", "max_telomere_start"),
                              ("min_density_threshold", "density_threshold"), ("short_telomere_threshold", "short_telomere_threshold_bp")):
                value = params.get(key)
                if value is not None:
                    getattr(self, name).setText(format(value*100, '.6g') if name == 'min_density_threshold' else str(value))
        except (OSError, ValueError, KeyError):
            # Input validation reports errors when Run is pressed; do not
            # display backend error messages inside the options panel.
            pass
