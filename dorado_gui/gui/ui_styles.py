from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QGroupBox
)
from PySide6.QtCore import Qt

"""Shared Qt style helpers for the Telomere Analyzer GUI."""


def apply_global_style(widget):
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