from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
)
from PySide6.QtCore import Qt

from gui.ui_styles import make_card


class OutputSection:
    """Mixin that builds the Output Path card used in the main UI."""

    def _build_output(self):
        """
        Construct the output path card.

        Returns:
            QWidget: styled card widget containing the output path row.
        """
        box = make_card("Output Path")
        box.setStyleSheet(box.styleSheet() + """
            QGroupBox {
                padding-top: 12px;
            }
        """)

        layout = QVBoxLayout()

        # Build and store the output row (layout + QLineEdit)
        self.output_input = self._path_row(
            "Output",
            "Select output path..."
        )

        layout.addLayout(
            self.output_input["layout"]
        )

        box.setLayout(layout)

        return box

    def _path_row(self, label: str, placeholder: str):
        """
        Create a horizontal row with a label, line edit and folder button.

        Args:
            label: text for the left label.
            placeholder: placeholder text for the QLineEdit.

        Returns:
            dict: { "layout": QHBoxLayout, "edit": QLineEdit }
        """
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignLeft)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        lbl.setStyleSheet("font-weight: bold;")

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)

        def browse():
            path = QFileDialog.getExistingDirectory(self, f"Select {label}")
            if path:
                edit.setText(path)

        # Uses _create_folder_button from the InputSection / AppWindow mixin
        btn = self._create_folder_button(browse)

        layout.addWidget(lbl)
        layout.addWidget(edit)
        layout.addWidget(btn)

        return {"layout": layout, "edit": edit}
