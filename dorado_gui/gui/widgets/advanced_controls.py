"""Reusable help labels, constrained checkboxes and toggle switches."""
from PySide6.QtWidgets import QLabel, QCheckBox, QMessageBox
from PySide6.QtCore import Qt, QSize, QRectF, QPoint
from PySide6.QtGui import QColor, QCursor, QPainter


class HoverHelpLabel(QLabel):
    """Label with a consistently styled cross-platform help popup."""

    def __init__(self, text, help_text):
        super().__init__(text)
        self._help_popup = QLabel(help_text, None, Qt.ToolTip)
        self._help_popup.setStyleSheet("""
            QLabel {
                color: #000000;
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                font-size: 11px;
                padding: 3px 5px;
            }
        """)

    def enterEvent(self, event):
        """Show help beside the pointer when the label is hovered."""
        self._help_popup.adjustSize()
        self._help_popup.move(QCursor.pos() + QPoint(10, 12))
        self._help_popup.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide help when the pointer leaves the label."""
        self._help_popup.hide()
        super().leaveEvent(event)


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


