from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
)

from pathlib import Path
from PySide6.QtGui import QIcon
from gui.ui_styles import make_card
from gui.widgets.selection_widgets import SelectCard
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
        """
        Construct the Input Data card containing selection cards and path row.

        Returns:
            QWidget: a styled card widget (from make_card) containing the input UI.
        """
        self.selected_input = "pod5"
        self.cards = {}
        
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Select input directory...")

        box = make_card("Input Data")
        layout = QVBoxLayout(box)
        layout.setSpacing(16)

        subtitle = QLabel("Select your input data type")
        subtitle.setStyleSheet("color: #6b7280; font-size: 13px; background-color: white;")
        layout.addWidget(subtitle)

        row = QHBoxLayout()
        row.setSpacing(20)

        for key, label, desc in [
            ("pod5", "POD5 (Raw Signals)", "Start from raw POD5 files.\nBasecalling will be performed."),
            ("bam", "BAM (Basecalled)", "Use existing basecalled BAM files.\nSkip basecalling step."),
            ("fastq", "FASTQ", "Use existing FASTQ files."),
        ]:
            card = SelectCard(key, label, desc, theme="blue")
            card.mousePressEvent = lambda e, k=key: self._select_input(k)
            self.cards[key] = card
            row.addWidget(card)

        layout.addLayout(row)

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

        return box

    def _select_input(self, key):
        """
        Mark the given input card as selected and update visuals.

        Args:
            key (str): one of "pod5", "bam", "fastq".
        """
        self.selected_input = key
        for k, card in self.cards.items():
            card.set_selected(k == key)

    def _browse_input(self, edit=None):
        """
        Open a directory picker and place the chosen path into the provided QLineEdit.

        Args:
            edit (QLineEdit|None): widget to fill; if None uses self.input_path.
        """
        if edit is None:
            edit = self.input_path
        path = QFileDialog.getExistingDirectory(self, "Select input")
        if path:
            edit.setText(path)

    def get_selected_inputs(self):
        """
        Return the selected input paths according to the current UI selection.

        Returns:
            dict: keys: 'pod5', 'fastq', 'bam', 'nanotel' with path strings (empty if not selected).
        """
        return {
            "pod5": self.input_path.text() if self.selected_input == "pod5" else "",
            "fastq": self.input_path.text() if self.selected_input == "fastq" else "",
            "bam": self.input_path.text() if self.selected_input == "bam" else "",
            "nanotel": "",
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
