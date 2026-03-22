import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QHBoxLayout, QComboBox,
    QTextEdit, QGroupBox, QDialog
)
from PySide6.QtCore import Qt

def apply_global_style(widget):
    widget.setStyleSheet("""
        QWidget {
            background-color: #f0f2f5;
            font-family: Segoe UI;
            color: #2c2c2c;   /* 🔥 main text (dark gray, not black) */
        }

        QLabel {
            color: #2c2c2c;
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

        QLineEdit::placeholder {
            color: #9aa0a6;   /* 🔥 light gray placeholder like screenshot */
        }

        QComboBox {
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            background: white;
            color: #2c2c2c;
        }

        QPushButton {
            border-radius: 10px;
            padding: 10px;
            color: #2c2c2c;
        }

        QTextEdit {
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            background: white;
            color: #2c2c2c;
        }
    """)

def make_card(title):
    box = QGroupBox(title)
    box.setStyleSheet("""
        QGroupBox {
            background: #f6f7f9;
            border-radius: 14px;
            padding: 15px;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            top: -5px;
            padding: 0 5px;
        }
    """)
    return box


class AppWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telomere Analyzer")
        self.resize(700, 800)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout()

        # HEADER
        header = QLabel("Telomere Analyzer")
        header.setAlignment(Qt.AlignLeft)
        header.setStyleSheet("""
            QLabel {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4b7b83, stop:1 #3c63d2
                );
                color: white;
                font-size: 28px;
                font-weight: 900;
                padding: 20px;
                border-radius: 14px;
            }
        """)
        main_layout.addWidget(header)

        # INPUTS
        input_box = make_card("Input Paths")
        input_layout = QVBoxLayout()

        self.pod5_input = self._path_row("POD5", "Select POD5 directory...")
        self.fastq_input = self._path_row("FASTQ", "Select FASTQ directory...")
        self.bam_input = self._path_row("BAM", "Select BAM directory...")
        self.nanotel_input = self._path_row("NanoTel", "Select NanoTel directory...")

        for row in [self.pod5_input, self.fastq_input, self.bam_input, self.nanotel_input]:
            input_layout.addLayout(row["layout"])

        input_box.setLayout(input_layout)
        main_layout.addWidget(input_box)

        # OUTPUT
        output_box = make_card("Output Directory")
        output_layout = QVBoxLayout()
        self.output_input = self._path_row("Output", "Select output directory...")
        output_layout.addLayout(self.output_input["layout"])
        output_box.setLayout(output_layout)
        main_layout.addWidget(output_box)

        # CONFIG
        config_box = make_card("Configuration")
        config_layout = QVBoxLayout()

        self.organism = QComboBox()
        self.organism.addItems(["mouse", "human"])

        config_layout.addWidget(QLabel("Organism"))
        config_layout.addWidget(self.organism)

        config_box.setLayout(config_layout)
        main_layout.addWidget(config_box)

        # WORKFLOW
        workflow_box = make_card("Quick Setup")
        workflow_layout = QVBoxLayout()

        self.workflow_mode = QComboBox()
        self.workflow_mode.addItems([
            "Complete POD5 Workflow",
            "FASTQ Workflow",
            "NanoTel Only",
            "Alignment Only"
        ])

        workflow_layout.addWidget(QLabel("Workflow mode"))
        workflow_layout.addWidget(self.workflow_mode)

        bottom_layout = QHBoxLayout()
        note = QLabel("Choose a high-level mode. All internal steps are auto-configured.")
        note.setStyleSheet("color: gray; font-size: 11px;")
        bottom_layout.addWidget(note)
        bottom_layout.addStretch()

        self.advanced_btn = QPushButton("⚙ Advanced options")
        self.advanced_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #d0d0d0;
                padding: 6px 10px;
                font-size: 12px;
                border-radius: 8px;
                color: #555;
            }
            QPushButton:hover {
                background: #eaecef;
            }
        """)
        bottom_layout.addWidget(self.advanced_btn)

        workflow_layout.addLayout(bottom_layout)

        workflow_box.setLayout(workflow_layout)
        main_layout.addWidget(workflow_box)


        # ===== MAIN BUTTONS =====
        btn_layout = QHBoxLayout()

        self.run_btn = QPushButton("▶ Run Workflow")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 14px;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.run_btn.clicked.connect(self.show_log_dialog)

        self.cancel_btn = QPushButton("✖ Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #555;
                font-size: 14px;
                padding: 14px;
                border-radius: 12px;
            }
        """)

        btn_layout.addWidget(self.run_btn, 2)
        btn_layout.addWidget(self.cancel_btn, 1)

        main_layout.addLayout(btn_layout)

        # LOG (created but not shown in main UI)
        self.log = QTextEdit()
        self.log.setMinimumHeight(150)
        self.log.setReadOnly(True)

        # FINAL
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.setLayout(main_layout)
        apply_global_style(self)

    def _path_row(self, label, placeholder):
        layout = QHBoxLayout()

        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        lbl.setStyleSheet("font-weight: bold;")

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)

        btn = QPushButton("📁")
        btn.setFixedWidth(40)
        btn.setStyleSheet("padding: 8px;")

        def browse():
            path = QFileDialog.getExistingDirectory(self, f"Select {label}")
            if path:
                edit.setText(path)

        btn.clicked.connect(browse)

        layout.addWidget(lbl)
        layout.addWidget(edit)
        layout.addWidget(btn)

        return {"layout": layout, "edit": edit}

    def show_log_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Execution Log")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Execution Log"))
        layout.addWidget(self.log)
        dialog.setLayout(layout)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.show()
        dialog.resize(self.size())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())