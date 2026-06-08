"""
Action section - run / cancel buttons.

Provides a reusable mixin that builds the action button row used by the main UI.
"""
from PySide6.QtWidgets import (
    QPushButton,
    QHBoxLayout,
)


class ActionSection:
    """Mixin that exposes _build_buttons() to create the action button layout."""

    def _build_buttons(self):
        """
        Build the horizontal layout containing Run and Cancel buttons.

        Returns:
            QHBoxLayout: layout containing configured Run and Cancel QPushButton widgets.
        """
        layout = QHBoxLayout()

        # Primary action button: Run workflow
        self.run_btn = QPushButton("▶ Run Workflow")
        # Connect to the window's log dialog/show handler
        self.run_btn.clicked.connect(self.show_log_dialog)

        # Secondary action button: Cancel / close
        self.cancel_btn = QPushButton("✖ Cancel")
        # Connect to the window's cancel handler (stops worker or closes window)
        self.cancel_btn.clicked.connect(self._handle_cancel)

        # Styles for the primary (run) button
        run_style = """
            QPushButton {
                background: #2563EB;
                color: white;
                border: 1px solid #2563EB;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1D4ED8;
                border: 1px solid #1D4ED8;
            }
            QPushButton:pressed {
                background: #1E40AF;
                border: 1px solid #1E40AF;
            }
        """

        # Styles for the secondary (cancel) button
        cancel_style = """
            QPushButton {
                background: white;
                color: #374151;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                border: 1px solid #2563EB;
                color: #2563EB;
                background: white;
            }
            QPushButton:pressed {
                background: #EFF6FF;
                border: 1px solid #2563EB;
                color: #2563EB;
            }
        """

        # Apply styles and assemble layout
        self.run_btn.setStyleSheet(run_style)
        self.cancel_btn.setStyleSheet(cancel_style)

        layout.addWidget(self.run_btn, 2)
        layout.addWidget(self.cancel_btn, 1)

        return layout