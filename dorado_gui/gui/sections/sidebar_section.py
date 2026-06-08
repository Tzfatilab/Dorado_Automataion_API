"""
Sidebar and section header builders for the main UI.

Provides:
- _build_sidebar(): left-hand navigation with app title and menu buttons.
- _build_section_header(): header shown at top of the content area.
- _select_menu(): helper to ensure only one menu button is active.

This is implemented as a mixin so the AppWindow can include these builders.
"""
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt


class SidebarSection:
    """Mixin that supplies sidebar and section header UI construction methods."""

    def _build_sidebar(self):
        """
        Build the left-hand sidebar widget.

        The sidebar contains an icon/title header and a list of menu buttons.
        Returns:
            QWidget: configured sidebar widget ready to be inserted into the main layout.
        """
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # =========================
        # Header (icon + title)
        # =========================
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Icon (emoji placeholder)
        icon = QLabel("🧬")
        icon.setStyleSheet("font-size: 26px;")

        # Title + subtitle container
        title_container = QWidget()
        title_container.setStyleSheet("""
            background: transparent;
            color: white;
        """)

        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title = QLabel("Telomere Analyzer")
        title.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: 700;
        """)

        subtitle = QLabel("Dorado Workflow")
        subtitle.setStyleSheet("""
            background: transparent;
            color: #94a3b8;
            font-size: 12px;
        """)

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addWidget(icon)
        header_layout.addWidget(title_container)

        layout.addWidget(header)
        layout.addSpacing(10)

        # =========================
        # Menu buttons
        # =========================
        # Store buttons for selection management
        self.menu_buttons = {}

        # Define menu items as (label, icon_text)
        menu_items = [
            ("Pipeline Setup", "⚙️"),
            # Additional items can be added here if needed
            # ("Run Summary", "📄"),
            # ("Log Viewer", "🧾"),
        ]

        for name, icon_text in menu_items:
            # Create a styled push button for each menu item
            btn = QPushButton(f"{icon_text}  {name}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)

            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #cbd5f5;
                    text-align: left;
                    padding: 12px;
                    border-radius: 10px;
                    font-size: 13px;
                }

                QPushButton:hover {
                    background: rgba(255,255,255,0.05);
                }

                QPushButton:checked {
                    background: #3c63d2;
                    color: white;
                }
            """)

            # Ensure only one button remains selected
            btn.clicked.connect(lambda _, b=btn: self._select_menu(b))

            layout.addWidget(btn)
            self.menu_buttons[name] = btn

        # Default select first menu item if present
        if self.menu_buttons:
            list(self.menu_buttons.values())[0].setChecked(True)

        layout.addStretch()

        return sidebar

    def _build_section_header(self):
        """
        Build the content area section header.

        Returns:
            QWidget: header container with title and subtitle describing the current panel.
        """
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("Configure Your Analysis Pipeline")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
        """)
        title.setFixedHeight(24)

        subtitle = QLabel("Select data type, choose analysis steps, and configure options.")
        subtitle.setStyleSheet("""
            color: #6b7280;
            font-size: 12px;
        """)
        subtitle.setFixedHeight(18)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return container

    def _select_menu(self, selected_button):
        """
        Mark the given menu button as selected and unselect others.

        Args:
            selected_button (QPushButton): the button that was clicked.

        Returns:
            None
        """
        for button in self.menu_buttons.values():
            button.setChecked(button == selected_button)