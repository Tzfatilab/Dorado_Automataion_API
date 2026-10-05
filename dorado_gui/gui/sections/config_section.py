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

    def _build_profile_selector(self):
        """Profile choice anchored at the bottom of the sidebar."""
        profile_row = QVBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(8)
        profile_label = QLabel("Profile")
        profile_label.setStyleSheet("font-weight: 700; color: #cbd5e1; background: transparent;")
        self.run_profile = QComboBox()
        self.run_profile.setMinimumWidth(0)
        self.run_profile.setFixedHeight(30)
        self.run_profile.setStyleSheet("""
            QComboBox { padding: 3px 10px; background: white; color: #2563eb; }
            QComboBox QAbstractItemView {
                background: white; color: #2563eb;
                selection-background-color: white; selection-color: #2563eb;
            }
            QComboBox QAbstractItemView::item:selected { background: white; color: #2563eb; }
        """)
        self.run_profile.setAccessibleName("Run configuration profile")
        self.run_profile.setToolTip("Choose the saved configuration for the next run.")
        self.run_profile.currentTextChanged.connect(self._select_run_profile)
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.run_profile)
        return profile_row


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

        # Organism can still be overridden for this run.
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
            "Mouse",
            "Human",
            "Zebra Fish"
        ])
        self.organism.setMinimumWidth(260)

        row.addWidget(label)
        row.addWidget(self.organism, 1)

        layout.addLayout(row)

        box.setLayout(layout)

        return box
