"""
Advanced options section for the main UI.

Contains basecalling and NanoTel option cards and related helpers.

The controls in this mixin are read by AppWindow when it creates a worker.
Their enabled state follows the workflow selections managed by WorkflowSection.
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
    QGraphicsOpacityEffect,
    QMessageBox,
)

from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
    QIntValidator,
    QDoubleValidator,
    QRegularExpressionValidator,
)
from PySide6.QtCore import QRegularExpression

from gui.ui_styles import make_card
from gui.widgets.selection_widgets import SelectOption
from core.workflow_constants import BASE_DIR


class MappingCheckBox(QCheckBox):
    """Checkbox that can block unchecking when mapping is required."""

    def __init__(self, text, can_uncheck):
        super().__init__(text)
        self.can_uncheck = can_uncheck

    def nextCheckState(self):
        # Intercept the click before Qt visually unchecks the box. Restoring the
        # state from a clicked handler would cause a short unchecked flicker.
        if self.isChecked() and not self.can_uncheck():
            QMessageBox.warning(
                self.window(),
                "Mapping Required",
                "Chromosome mapping cannot be disabled while methylation is selected.",
            )
            return

        super().nextCheckState()


class ToggleSwitch(QCheckBox):
    """Small switch control with a sliding knob."""

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 22)
        self.toggled.connect(lambda _: self.update())

    def sizeHint(self):
        return QSize(42, 22)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setChecked(not self.isChecked())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track = QRectF(1, 2, 40, 18)
        checked = self.isChecked()
        track_color = QColor("#2563EB") if checked else QColor("#E5E7EB")
        border_color = QColor("#2563EB") if checked else QColor("#D1D5DB")
        knob_x = 22 if checked else 3

        painter.setPen(border_color)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 9, 9)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, 4, 14, 14))


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

        self.basecalling_options_card = self._build_basecalling_options()
        self.nanotel_options_card = self._build_nanotel_options()

        # Keep references because WorkflowSection refreshes these cards whenever
        # the user selects or deselects an analysis step.
        row.addWidget(self.basecalling_options_card, 1)
        row.addWidget(self.nanotel_options_card, 1)
        box.setLayout(row)

        self._update_advanced_options_state()

        return box

    def _update_advanced_options_state(self):
        """Enable advanced option cards only for selected workflow steps."""
        # getattr keeps construction safe if this mixin is reused before
        # WorkflowSection has initialized selected_workflows.
        selected = getattr(self, "selected_workflows", set())
        self._set_option_card_enabled(
            self.basecalling_options_card,
            "basecalling" in selected,
        )
        self._set_option_card_enabled(
            self.nanotel_options_card,
            "nanotel" in selected,
        )

    @staticmethod
    def _set_option_card_enabled(card, enabled):
        """Set card interactivity and clearly fade disabled cards."""
        # Reuse one opacity effect per card; replacing it on every workflow
        # click can make Qt discard the previous effect unexpectedly.
        effect = card.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(card)
            card.setGraphicsEffect(effect)

        effect.setOpacity(1.0 if enabled else 0.45)
        card.setEnabled(enabled)

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
        """Build the card containing basecalling-specific controls."""
        card = self._option_card()
        main = QVBoxLayout(card)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_basecalling_header())
        main.addWidget(self._build_divider(QFrame.HLine))
        main.addWidget(self._build_basecalling_body())

        return card

    def _build_basecalling_header(self):
        """Build the Basecalling Options card header."""
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
        icon.setStyleSheet("background: transparent; border: none;")
        icon.setPixmap(
            QPixmap(str(BASE_DIR / "icons" / "sub_basecalling.png")).scaled(
                34,
                34,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        title = QLabel("Basecalling Options")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2563eb;
            border: none;
            background: transparent;
        """)

        title_row.addWidget(icon)
        title_row.addSpacing(6)
        title_row.addWidget(title)
        title_row.addStretch()
        header.addLayout(title_row)
        header.addStretch()

        return header_widget

    @staticmethod
    def _build_divider(shape):
        """Build a horizontal or vertical divider."""
        line = QFrame()
        line.setFrameShape(shape)
        size_rule = "max-height: 1px;" if shape == QFrame.HLine else "max-width: 1px;"
        line.setStyleSheet(f"""
            color: #E5E7EB;
            background: #E5E7EB;
            {size_rule}
        """)
        return line

    def _build_basecalling_body(self):
        """Build methylation and chromosome mapping controls."""
        body_widget = QWidget()
        body_widget.setStyleSheet("background: white;")
        body = QHBoxLayout(body_widget)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(16)

        body.addWidget(self._build_methylation_options())
        body.addWidget(self._build_divider(QFrame.VLine))
        body.addWidget(self._build_mapping_option())

        return body_widget

    def _build_methylation_options(self):
        """Build the mutually exclusive methylation selectors."""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        meth_title = QLabel("Methylation Type")
        meth_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            border: none;
            background: transparent;
        """)
        layout.addWidget(meth_title)

        self.none_option = SelectOption("None")
        self.cpg_option = SelectOption("5mCpG")
        self.hmc_option = SelectOption("5mCpG + 5hmCpG")
        self.none_option.set_selected(True)

        for option in [self.none_option, self.cpg_option, self.hmc_option]:
            layout.addWidget(option)
            # Capture the current option in the default argument. Without this,
            # every callback would select the final option from the loop.
            option.mousePressEvent = (
                lambda event, selected=option: self._set_methylation(selected)
            )

        widget = QWidget()
        widget.setLayout(layout)
        widget.setFixedWidth(360)
        return widget

    def _build_mapping_option(self):
        """Build the chromosome mapping control."""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        chrom_title = QLabel("Chromosome Mapping")
        chrom_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            border: none;
            background: transparent;
        """)
        layout.addWidget(chrom_title)

        self.chromosome_mapping = MappingCheckBox(
            "Align reads to reference genome\n"
            "during basecalling",
            # Mapping is mandatory while either methylation mode is selected.
            # The callback is evaluated on each click, not only during setup.
            can_uncheck=lambda: self.none_option.selected,
        )

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
        layout.addWidget(self.chromosome_mapping)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_nanotel_options(self):
        """Build the card containing NanoTel-specific controls."""
        card = self._option_card()
        main = QVBoxLayout(card)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_nanotel_header())
        main.addWidget(self._build_divider(QFrame.HLine))
        main.addWidget(self._build_nanotel_body())

        return card

    def _build_nanotel_header(self):
        """Build the NanoTel Options card header."""
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
        icon.setStyleSheet("background: transparent; border: none;")
        icon.setPixmap(
            QPixmap(str(BASE_DIR / "icons" / "sub_nanotel.png")).scaled(
                34,
                34,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        title = QLabel("NanoTel Options")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #2563EB;
            background: transparent;
            border: none;
        """)

        title_row.addWidget(icon)
        title_row.addSpacing(6)
        title_row.addWidget(title)
        title_row.addStretch()

        header.addLayout(title_row)
        header.addStretch()
        summary_toggle = QWidget()
        summary_toggle.setCursor(Qt.PointingHandCursor)
        summary_toggle.setStyleSheet("background: transparent; border: none;")
        summary_layout = QHBoxLayout(summary_toggle)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)

        summary_label = QLabel("Summary only")
        summary_label.setCursor(Qt.PointingHandCursor)
        summary_label.setStyleSheet("""
            QLabel {
                color: #4B5563;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
        """)

        self.summary_only = ToggleSwitch()
        self.summary_only.setToolTip(
            "Skip per-read FASTA/plot files and create only summary outputs."
        )
        self.summary_only.setChecked(False)
        summary_layout.addWidget(summary_label)
        summary_layout.addWidget(self.summary_only)
        summary_toggle.mouseReleaseEvent = self._toggle_summary_only_from_row
        summary_label.mouseReleaseEvent = self._toggle_summary_only_from_row
        header.addWidget(summary_toggle)

        return header_widget

    def _toggle_summary_only_from_row(self, event):
        """Toggle summary-only mode when the label or surrounding row is clicked."""
        if event.button() == Qt.LeftButton and self.summary_only.isEnabled():
            self.summary_only.setChecked(not self.summary_only.isChecked())
            event.accept()
            return
        event.ignore()

    def _build_nanotel_body(self):
        """Build the TVR mode controls and numeric NanoTel fields."""
        body_widget = QWidget()
        body_widget.setStyleSheet("background: white;")
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)

        body.addLayout(self._build_tvr_mode_controls())
        body.addLayout(self._build_nanotel_fields())

        return body_widget

    def _build_nanotel_mapping_option(self):
        """Build the mapping toggle for NanoTel workflows."""
        self.nanotel_mapping = QCheckBox(
            "Run mapping"
        )

        self.nanotel_mapping.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #111827;
                spacing: 10px;
                border: none;
                background: transparent;
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

        return self.nanotel_mapping

    def _build_tvr_mode_controls(self):
        """Build the segmented TVR mode buttons."""
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
        # Manual patterns are stored here even though the field itself is not
        # displayed; AppWindow reads the value when it creates the worker.
        self.tvr_manual = QLineEdit()

        active_style, segmented_style = self._tvr_button_styles()
        for button in self.tvr_buttons:
            # Capture each button so its callback keeps the correct TVR mode.
            button.clicked.connect(
                lambda _, selected=button: self._set_tvr_mode(
                    selected,
                    active_style,
                    segmented_style,
                )
            )
            button.setStyleSheet(
                active_style if button == self.none_btn else segmented_style
            )

        button_widths = [72, 96, 72, 104]
        for button, width in zip(self.tvr_buttons, button_widths):
            button.setFixedWidth(width)
            button.setFixedHeight(34)
            tvr_row.addWidget(button)

        tvr_row.addStretch()
        return tvr_row

    @staticmethod
    def _tvr_button_styles():
        """Return active and inactive TVR button styles."""
        inactive_style = """
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
        return active_style, inactive_style

    def _build_nanotel_fields(self):
        """Build validated numeric NanoTel configuration fields."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.read_length = QLineEdit("2000")
        self.max_distance_edge = QLineEdit("134")
        self.min_density_threshold = QLineEdit("0.75")

        self.read_length.setFixedWidth(74)
        self.max_distance_edge.setFixedWidth(74)
        self.min_density_threshold.setFixedWidth(74)

        # Validators prevent invalid values before the options reach the
        # pipeline configuration layer.
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
        read_label = self._build_field_label("Min Read Length (bp)", 140, label_style)
        edge_label = self._build_field_label("Max Edge Distance", 140, label_style)
        density_label = self._build_field_label("Min Density", 128, label_style)

        grid.addWidget(read_label, 0, 0)
        grid.addWidget(self.read_length, 0, 1)
        grid.addWidget(edge_label, 0, 2)
        grid.addWidget(self.max_distance_edge, 0, 3)
        grid.addWidget(density_label, 1, 0)
        grid.addWidget(self.min_density_threshold, 1, 1)
        grid.addWidget(self._build_nanotel_mapping_option(), 1, 2, 1, 2)
        return grid

    @staticmethod
    def _build_field_label(text, width, style):
        """Build a fixed-width label for a NanoTel field."""
        label = QLabel(text)
        label.setStyleSheet(style)
        label.setWordWrap(False)
        label.setFixedWidth(width)
        return label

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
        line_edit.setPlaceholderText("ACTG TTAGGG")
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

        # Normalize every accepted separator into the comma-separated format
        # expected by the NanoTel configuration override.
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

        methylation_enabled = selected != self.none_option
        if methylation_enabled:
            # Methylation analysis depends on aligned reads. Mapping remains
            # selected after methylation is removed, but can then be unchecked.
            self.chromosome_mapping.setChecked(True)

    def _get_methylation_type(self):
        """
        Query the currently selected methylation type.

        Returns:
            str: one of "none", "5mCpG", "5mCpG + 5hmCpG".
        """
        if self.none_option.selected:
            return "none"

        if self.cpg_option.selected:
            return "5mCG"

        if self.hmc_option.selected:
            return "5mCG_5hmCG"

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
        row.addStretch()
        return row
