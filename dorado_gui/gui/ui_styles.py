from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QGroupBox
)
from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QColor, QPalette

"""Shared Qt style helpers for the Telomere Analyzer GUI."""


def apply_global_style(widget):
    # Tooltips are top-level windows on some platforms, so style them on the
    # application rather than relying on the main window's stylesheet.
    app = QApplication.instance()
    if app is not None:
        tooltip_palette = app.palette()
        tooltip_palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        tooltip_palette.setColor(QPalette.ToolTipText, QColor("#000000"))
        app.setPalette(tooltip_palette)
        app.setStyleSheet("""
            QToolTip {
                color: #000000;
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                font-size: 11px;
                padding: 3px 5px;
            }
        """)

    widget.setStyleSheet("""
        QWidget { background-color: #f0f2f5; }

        QLabel#mainHeader {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #0f172a,
                stop:1 #1e293b
            );
            color: white;
            font-size: 20px;
            font-weight: 700;
            padding: 10px 12px;
            border-radius: 10px;
        }

        QLabel { color: #2c2c2c; }

        QToolTip {
            color: #000000;
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            font-size: 11px;
            padding: 3px 5px;
        }

        #content {
            background-color: #ffffff;
        }
        QGroupBox {
            color: #2c2c2c;
            font-weight: bold;
        }

        QLineEdit {
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            background: white;
            color: #2c2c2c;
        }

        QComboBox {
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            background: white;
            color: #2c2c2c;
        }

        QComboBox QAbstractItemView {
            background: white;
            color: #2c2c2c;
            selection-background-color: #3c63d2;
            selection-color: white;
        }
        QTextEdit {
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            background: white;
            color: #2c2c2c; 
        }

        QWidget#progressPanel {
            background: #f8fafc;
            border: 1px solid #d7dce1;
            border-radius: 8px;
        }

        QLabel#progressStageLabel,
        QLabel#progressLabel,
        QLabel#progressPercentLabel {
            font-family: sans-serif;
        }

        QLabel#progressStageLabel {
            color: #1e293b;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#progressLabel, QLabel#progressPercentLabel {
            color: #334155;
            font-size: 13px;
            font-weight: 400;
        }

        QLabel#progressPercentLabel { min-width: 44px; }

        QProgressBar#workflowProgress {
            min-height: 12px;
            max-height: 12px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            background: #e2e8f0;
            color: #0f172a;
            text-align: center;
            font-weight: 600;
        }

        QProgressBar#workflowProgress::chunk {
            border-radius: 5px;
            background-color: #4A6EDB;
        }


        QWidget#sidebar {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #0f172a,
                stop:1 #1e293b
            );
            border-right: 1px solid #1e293b;
        }

        QLabel {
            color: #2c2c2c;
        }
                         
        QWidget#sidebar QPushButton {
            background: transparent;
            color: white;
            text-align: left;
            padding: 10px;
            border-radius: 8px;
        }

        QPushButton#primaryButton {
            background-color: #4A6EDB;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px;
            font-weight: 600;
        }

        QPushButton#primaryButton:hover {
            background-color: #3f5ec0;
        }

        QPushButton#primaryButton:pressed {
            background-color: #364fa8;
        }

        QPushButton:disabled {
            background-color: #9ca3af;
            color: #e5e7eb;
        }
        QWidget#sidebar QPushButton:hover {
            background: rgba(255,255,255,0.05);
        }

        QWidget#sidebar QPushButton:checked {
            background: #3c63d2;
        }
                         
        QMessageBox QPushButton {
            background: white;
            color: #111827;
            border: 1px solid #D1D5DB;
            border-radius: 6px;
            padding: 6px 14px;
            min-width: 70px;
        }

        QMessageBox QPushButton:hover {
            border: 1px solid #2563EB;
            color: #2563EB;
        }

        QMessageBox QPushButton:pressed {
            background: #EFF6FF;
        }
    """)


# =========================================================
# FIXED CARD (compatible with your existing GUI)
# =========================================================
def make_card(title):
    box = QGroupBox(title)
    box.setAttribute(Qt.WA_StyledBackground, True)

    box.setStyleSheet("""
        QGroupBox {
            background: white;
            border-radius: 14px;
            padding: 8px;
            font-weight: 700;
            font-size: 16px;   
            margin-top: 0px;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            top: -4px;
            padding: 2px 6px 10px 6px;
        }
    """)
    return box


class _HelpButtonPositioner(QObject):
    """Place help at the right end of a subtitle line without layout changes."""

    def __init__(self, parent, button, anchor):
        super().__init__(parent)
        self.card = parent
        self.button = button
        self.anchor = anchor

    def place(self):
        anchor_pos = self.anchor.mapTo(self.card, QPoint(0, 0))
        x = max(0, self.card.width() - self.button.width() - 12)
        y = anchor_pos.y() + (self.anchor.height() - self.button.height()) // 2
        self.button.move(x, y)
        self.button.raise_()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Move, QEvent.Show,
                            QEvent.FontChange, QEvent.StyleChange):
            self.place()
        return False


def make_help_button(parent, title, message, anchor):
    """Overlay section help on the subtitle line without changing geometry."""
    from PySide6.QtWidgets import QToolButton

    button = QToolButton(parent)
    button.setText("?")
    button.setToolTip(f"About {title}")
    button.setAccessibleName(f"Help for {title}")
    button.setFixedSize(30, 30)
    button.setStyleSheet("""
        QToolButton {
            color: #2563eb;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
        }
        QToolButton:hover { background: #dbeafe; }
    """)
    button.clicked.connect(lambda: _show_help_dialog(parent, title, message))
    positioner = _HelpButtonPositioner(parent, button, anchor)
    parent.installEventFilter(positioner)
    anchor.installEventFilter(positioner)
    positioner.place()
    return button


def _show_help_dialog(parent, title, message):
    """Show section guidance in a readable, scrollable window."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser

    dialog = QDialog(parent)
    dialog.setWindowTitle(f"About {title}")
    dialog.setMinimumWidth(480)
    dialog.resize(580, 460)
    dialog.setStyleSheet("""
        QDialog { background: #ffffff; }
        QTextBrowser {
            background: #ffffff;
            color: #1f2937;
            border: none;
            font-size: 13px;
            padding: 16px 20px;
        }
        QPushButton {
            background: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 7px 18px;
            font-weight: 600;
        }
        QPushButton:hover { background: #1d4ed8; }
    """)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    content = QTextBrowser(dialog)
    content.setOpenExternalLinks(False)
    content.setHtml(message)
    layout.addWidget(content)
    buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
