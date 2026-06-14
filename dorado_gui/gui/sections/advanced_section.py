"""
Advanced options section for the main UI.

Contains basecalling and NanoTel option cards and related helpers.
"""
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QWidget,
    QGridLayout,
    QCheckBox,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
)

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPixmap,
    QIntValidator,
    QDoubleValidator,
    QRegularExpressionValidator,
)
from PySide6.QtCore import QRegularExpression

from gui.ui_styles import make_card
from gui.widgets.selection_widgets import SelectOption
from core.workflow_constants import BASE_DIR


class AdvancedSection:
    """Mixin providing the advanced options UI used by the main window."""

    def _build_advanced_options(self):
        """
        Build the container with Basecalling and NanoTel option cards.

        Returns:
            QWidget (card): A styled container widget that holds the two option cards.
        """
        box = make_card("Advanced Options")

        row = QHBoxLayout()
        row.setSpacing(16)

        row.addWidget(self._build_basecalling_options(), 1)
        row.addWidget(self._build_nanotel_options(), 1)
        box.setLayout(row)

        return box

    def _option_card(self):
        """
        Create a standardized option card frame with base styling.

        Returns:
            QFrame: styled frame to be used as an options card container.
        """
        card = QFrame()

        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        return card

    def _build_basecalling_options(self):
        """
        Build the 'Basecalling Options' card.

        This card includes methylation type selectors and a chromosome mapping checkbox.

        Returns:
            QFrame: fully configured basecalling options card.
        """
        card = self._option_card()

        main = QVBoxLayout(card)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # =====================================================
        # HEADER
        # =====================================================

        header_widget = QWidget()
        header_widget.setFixedHeight(55)

        header_widget.setStyleSheet("""
            background: white;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        """)

        header = QHBoxLayout(header_widget)
        header.setContentsMargins(14, 10, 14, 10)

        title_row = QHBoxLayout()

        icon = QLabel()
        icon.setStyleSheet("""
            background: transparent;
            border: none;
        """)
        icon.setPixmap(
            QPixmap(str(BASE_DIR / "icons" / "sub_basecalling.png")).
            scaled(34, 34,Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

        title = QLabel("Basecalling Options")

        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2F5FE3;
        """)

        title_row.addWidget(icon)
        title_row.addSpacing(6)
        title_row.addWidget(title)
        title_row.addStretch()
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2563eb;
            border: none;            
            background: transparent;
        """)

        header.addLayout(title_row)
        header.addStretch()

        main.addWidget(header_widget)

        # =====================================================
        # DIVIDER
        # =====================================================

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("""
            color: #E5E7EB;
            background: #E5E7EB;
            max-height: 1px;
        """)
        main.addWidget(line)

        # =====================================================
        # BODY
        # =====================================================

        body_widget = QWidget()
        body_widget.setStyleSheet("""
            background: white;
        """)
        body = QHBoxLayout(body_widget)

        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(16)

        # -----------------------------------------------------
        # LEFT SIDE: METHYLATION TYPE OPTIONS
        # -----------------------------------------------------

        left = QVBoxLayout()
        left.setAlignment(Qt.AlignTop)
        left.setSpacing(8)

        meth_title = QLabel("Methylation Type")
        meth_title.setStyleSheet("""
          font-size: 14px;
            font-weight: 600;
            color: #374151;
            border: none;
            background: transparent;
        """)
        left.addWidget(meth_title)

        # Reusable selectable options (provided by widgets.selection_widgets)
        self.none_option = SelectOption("None")
        self.cpg_option = SelectOption("5mCpG")
        self.hmc_option = SelectOption("5mCpG + 5hmCpG")

        # Default selection
        self.none_option.set_selected(True)

        left.addWidget(self.none_option)
        left.addWidget(self.cpg_option)
        left.addWidget(self.hmc_option)

        # Wire click handlers to update selected state
        for option in [
            self.none_option,
            self.cpg_option,
            self.hmc_option
        ]:
            option.mousePressEvent = (
                lambda e, o=option:
                self._set_methylation(o)
            )

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(360)

        body.addWidget(left_widget)

        # -----------------------------------------------------
        # VERTICAL DIVIDER
        # -----------------------------------------------------

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet("""
            color: #E5E7EB;
            background: #E5E7EB;
            max-width: 1px;
        """)
        body.addWidget(vline)

        # -----------------------------------------------------
        # RIGHT SIDE: CHROMOSOME MAPPING
        # -----------------------------------------------------

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignTop)
        right.setSpacing(8)

        chrom_title = QLabel("Chromosome Mapping")
        chrom_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            border: none;
            background: transparent;
        """)
        right.addWidget(chrom_title)

        self.chromosome_mapping = QCheckBox(
            "Align reads to reference genome\n"
            "during basecalling"
        )

        # Style the checkbox and indicators
        self.chromosome_mapping.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #111827;
                spacing: 10px;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }

            QCheckBox::indicator:unchecked {
                background: white;
                border: 2px solid #9CA3AF;
                border-radius: 4px;
            }

            QCheckBox::indicator:checked {
                background: #2563EB;
                border: 2px solid #2563EB;
                border-radius: 4px;
            }
        """)

        right.addWidget(self.chromosome_mapping)

        right_widget = QWidget()
        right_widget.setLayout(right)

        body.addWidget(right_widget)

        main.addWidget(body_widget)

        return card

    def _build_nanotel_options(self):
        """
        Build the 'NanoTel Options' card.

        Includes TVR mode segmented buttons and numeric configuration fields.

        Returns:
            QFrame: fully configured NanoTel options card.
        """
        card = self._option_card()

        main = QVBoxLayout(card)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # =====================================================
        # HEADER
        # =====================================================

        header_widget = QWidget()
        header_widget.setFixedHeight(55)

        header_widget.setStyleSheet("""
            background: white;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border: none;            
            background: transparent;                                    
        """)

        header = QHBoxLayout(header_widget)
        header.setContentsMargins(14, 10, 14, 10)

        title_row = QHBoxLayout()

        icon = QLabel()
        icon.setStyleSheet("""
            background: transparent;
            border: none;
        """)
        icon.setPixmap(
           QPixmap(str(BASE_DIR / "icons" / "sub_nanotel.png")).
            scaled(34, 34,Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

        title = QLabel("NanoTel Options")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2F5FE3;
        """)

        title_row.addWidget(icon)
        title_row.addSpacing(6)
        title_row.addWidget(title)
        title_row.addStretch()
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2563EB;
            background: transparent;
            border: none;            
        """)

        toggle = QCheckBox()
        header.addLayout(title_row)
        header.addStretch()
        header.addWidget(toggle)
        main.addWidget(header_widget)

        # =====================================================
        # DIVIDER
        # =====================================================

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("""
            color: #E5E7EB;
            background: #E5E7EB;
            max-height: 1px;
        """)
        main.addWidget(line)

        # =====================================================
        # BODY
        # =====================================================

        body_widget = QWidget()
        body_widget.setStyleSheet("""
            background: white;
        """)
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)

        # -------------------------------------------------
        # TVR BUTTONS (segmented control)
        # -------------------------------------------------

        tvr_row = QHBoxLayout()
        tvr_row.setSpacing(8)
        tvr_label = QLabel("TVR Mode")
        tvr_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            border: none;            
            background: transparent;
        """)
        tvr_label.setFixedWidth(80)
        tvr_row.addWidget(tvr_label)

        self.none_btn = QPushButton("None")
        self.preset_btn = QPushButton("Use Preset")
        self.tsq1_btn = QPushButton("TSQ1")
        self.manual_btn = QPushButton("Manual")

        self.tvr_buttons = [
            self.none_btn,
            self.preset_btn,
            self.tsq1_btn,
            self.manual_btn
        ]
        self.selected_tvr_mode = "None"
        self.tvr_manual = QLineEdit()

        segmented_style = """
            QPushButton {
                background: white;
                color: #111827;
                border: 1px solid #D1D5DB;
                padding: 8px 14px;
                border-radius: 8px;
                font-size: 13px;
            }

            QPushButton:hover {
                border: 1px solid #2563EB;
                color: #2563EB;
            }
        """

        active_style = """
            QPushButton {
                background: #2563EB;
                color: white;
                border: 1px solid #2563EB;
                padding: 8px 14px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
        """

        # Connect each button to the mode setter with styles passed through
        for btn in self.tvr_buttons:
            btn.clicked.connect(
                lambda _, b=btn: self._set_tvr_mode(
                    b,
                    active_style,
                    segmented_style
                )
            )

        # Initial style states
        self.none_btn.setStyleSheet(active_style)
        self.preset_btn.setStyleSheet(segmented_style)
        self.tsq1_btn.setStyleSheet(segmented_style)
        self.manual_btn.setStyleSheet(segmented_style)

        button_widths = {
            self.none_btn: 72,
            self.preset_btn: 96,
            self.tsq1_btn: 72,
            self.manual_btn: 104,
        }
        for btn, width in button_widths.items():
            btn.setFixedWidth(width)
            btn.setFixedHeight(34)

        tvr_row.addWidget(self.none_btn)
        tvr_row.addWidget(self.preset_btn)
        tvr_row.addWidget(self.tsq1_btn)
        tvr_row.addWidget(self.manual_btn)
        tvr_row.addStretch()

        body.addLayout(tvr_row)

        # -------------------------------------------------
        # GRID: numeric configuration fields
        # -------------------------------------------------

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.read_length = QLineEdit("2000")
        self.max_distance_edge = QLineEdit("134")
        self.min_density_threshold = QLineEdit("0.75")

        self.read_length.setFixedWidth(74)
        self.max_distance_edge.setFixedWidth(74)
        self.min_density_threshold.setFixedWidth(74)

        # Validators ensure valid numeric ranges
        self.read_length.setValidator(QIntValidator(0, 10000))
        self.max_distance_edge.setValidator(QIntValidator(0, 1000))
        validator = QDoubleValidator(0.0, 1.0, 3)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.min_density_threshold.setValidator(validator)

        for widget in [
            self.read_length,
            self.max_distance_edge,
            self.min_density_threshold,
        ]:
            widget.setFixedHeight(34)

        label_style = """
            QLabel {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 14px;
                font-weight: 500;
            }
        """

        read_label = QLabel("Min Read Length (bp)")
        read_label.setStyleSheet(label_style)
        edge_label = QLabel("Max Edge Distance")
        edge_label.setStyleSheet(label_style)
        density_label = QLabel("Min Density")
        density_label.setStyleSheet(label_style)

        for label in [read_label, edge_label, density_label]:
            label.setWordWrap(False)

        read_label.setFixedWidth(140)
        density_label.setFixedWidth(128)
        edge_label.setFixedWidth(140)

        grid.addWidget(read_label, 0, 0)
        grid.addWidget(self.read_length, 0, 1)
        grid.addWidget(edge_label, 0, 2)
        grid.addWidget(self.max_distance_edge, 0, 3)
        grid.addWidget(density_label, 1, 0)
        grid.addWidget(self.min_density_threshold, 1, 1)
        body.addLayout(grid)

        main.addWidget(body_widget)

        return card

    def _set_tvr_mode(
        self,
        selected_btn,
        active_style,
        segmented_style
    ):
        """
        Update TVR segmented button visuals and record the selected mode.

        Args:
            selected_btn (QPushButton): the button that was selected.
            active_style (str): stylesheet for the active button.
            segmented_style (str): stylesheet for inactive buttons.

        Returns:
            None
        """
        if selected_btn == self.manual_btn:
            patterns = self._prompt_manual_tvr_patterns()
            if patterns is None:
                return
            self.tvr_manual.setText(patterns)

        for btn in self.tvr_buttons:
            if btn == selected_btn:
                btn.setStyleSheet(active_style)
            else:
                btn.setStyleSheet(segmented_style)
        self.selected_tvr_mode = "Enter Manual" if selected_btn == self.manual_btn else selected_btn.text()

    def _prompt_manual_tvr_patterns(self):
        """
        Ask for manual TVR patterns with DNA-letter validation.

        Returns:
            Uppercase comma-separated pattern string, or None if cancelled.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Manual TVR Patterns")
        dialog.setModal(True)
        dialog.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLabel {
                color: #111827;
                font-size: 13px;
            }
            QLineEdit {
                color: #111827;
                background: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 8px;
                min-width: 260px;
            }
            QPushButton {
                color: #111827;
                background: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                border-color: #2563EB;
            }
            QPushButton:default {
                color: white;
                background: #2563EB;
                border-color: #2563EB;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        label = QLabel("Patterns separated by spaces:")
        line_edit = QLineEdit(self.tvr_manual.text())
        line_edit.setPlaceholderText("ACTG,TTAGGG")
        line_edit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression("[ACGTacgt,;\\s]*"),
                line_edit
            )
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        return ",".join(
            pattern.strip().upper()
            for pattern in line_edit.text().replace(";", ",").replace(" ", ",").split(",")
            if pattern.strip()
        )

    def _set_methylation(self, selected):
        """
        Set the methylation selection, ensuring mutual exclusivity.

        Args:
            selected (SelectOption): the option chosen by the user.

        Returns:
            None
        """
        for option in [
            self.none_option,
            self.cpg_option,
            self.hmc_option
        ]:
            option.set_selected(
                option == selected
            )

    def _get_methylation_type(self):
        """
        Query the currently selected methylation type.

        Returns:
            str: one of "none", "5mCpG", "5mCpG + 5hmCpG".
        """
        if self.none_option.selected:
            return "none"

        if self.cpg_option.selected:
            return "5mCpG"

        if self.hmc_option.selected:
            return "5mCpG + 5hmCpG"

        return "none"

    def _form_row(self, text, widget):
        """
        Helper to create a labeled row with a widget for forms.

        Args:
            text (str): label text for the row.
            widget (QWidget): input widget placed to the right of the label.

        Returns:
            QHBoxLayout: layout containing the label and the widget.
        """
        row = QHBoxLayout()
        label = QLabel(text)
        label.setFixedWidth(140)

        widget.setFixedHeight(32)

        row.addWidget(label)
        row.addWidget(widget)

        r