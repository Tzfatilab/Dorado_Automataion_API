"""Configuration section for the main UI.

Provides organism selection used by the workflow configuration panel.
"""

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
)
from PySide6.QtCore import Qt

from gui.ui_styles import make_card


class ConfigSection:
    """Mixin that builds the Configuration card used in the main window."""

    def _build_config(self):
        """
        Construct the configuration UI card.

        Returns:
            QWidget: styled card widget containing organism selection controls.
        """
        box = make_card("Configuration")
        box.setStyleSheet(box.styleSheet() + """
            QGroupBox {
                padding-top: 12px;
            }
        """)
        layout = QVBoxLayout()

        # Single row: label + organism combobox
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignLeft)
        row.setSpacing(10)

        label = QLabel("Organism")
        label.setStyleSheet("font-weight: 700; color: #374151;")
        label.setFixedWidth(80)
        label.setAlignment(Qt.AlignVCenter)

        # Combobox containing supported organism presets.
        self.organism = QComboBox()
        self.organism.addItems([
            "mouse",
            "human",
            "zebra fish"
        ])
        self.organism.setFixedWidth(260)

        row.addWidget(label)
        row.addWidget(self.organism)

        layout.addLayout(row)

        box.setLayout(layout)

        return box
