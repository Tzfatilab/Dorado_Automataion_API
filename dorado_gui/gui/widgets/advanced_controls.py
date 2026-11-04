"""Reusable help labels, constrained checkboxes and toggle switches."""
from PySide6.QtWidgets import QLabel, QCheckBox, QMessageBox, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QPainter


class LockedTVRControls(QWidget):
    """Keep locked controls visible and explain clicks during recalculation."""

    def __init__(self, controls_layout):
        """Initialize the instance and its dependencies.

        Args:
            controls_layout: Layout containing the TVR controls to lock together.

        Returns:
            None; initializes the instance.
        """
        super().__init__()
        self.locked = False
        self.controls = QWidget(self)
        self.controls.setLayout(controls_layout)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controls)

    def setLocked(self, locked):
        """Setlocked.

        Args:
            locked: Whether the original settings must remain uneditable.

        Returns:
            None.
        """
        self.locked = locked
        self.controls.setEnabled(not locked)
        self.controls.setAttribute(Qt.WA_TransparentForMouseEvents, locked)

    def mousePressEvent(self, event):
        """Mousepressevent.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if self.locked and event.button() == Qt.LeftButton:
            QMessageBox.warning(
                self.window(),
                "TVR mode cannot be changed",
                "Recalculate results uses the original TVR settings. "
                "To change TVR mode, run NanoTel analysis again.",
            )
            event.accept()
            return
        super().mousePressEvent(event)


class HoverHelpLabel(QLabel):
    """Label with a consistently styled cross-platform help popup."""

    def __init__(self, text, help_text):
        """Initialize the instance and its dependencies.

        Args:
            text: Text to parse, display or write.
            help_text: Explanation displayed in the tooltip.

        Returns:
            None; initializes the instance.
        """
        super().__init__(text)
        self.setToolTip(help_text)


class MappingCheckBox(QCheckBox):
    """Checkbox that can block unchecking when mapping is required."""

    def __init__(self, text, can_uncheck):
        """Initialize the instance and its dependencies.

        Args:
            text: Text to parse, display or write.
            can_uncheck: Callback deciding whether the checked option may be cleared.

        Returns:
            None; initializes the instance.
        """
        super().__init__(text)
        self.can_uncheck = can_uncheck

    def nextCheckState(self):
        # Intercept the click before Qt visually unchecks the box. Restoring the
        # state from a clicked handler would cause a short unchecked flicker.
        """Nextcheckstate.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
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
        """Initialize the instance and its dependencies.

        Inputs:
            None; uses instance state.

        Returns:
            None; initializes the instance.
        """
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 22)
        self.toggled.connect(lambda _: self.update())

    def sizeHint(self):
        """Preferred widget size as QSize.

        Inputs:
            None; uses instance state.

        Returns:
            Preferred widget size as QSize.
        """
        return QSize(42, 22)

    def mouseReleaseEvent(self, event):
        """Mousereleaseevent.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setChecked(not self.isChecked())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Paintevent.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
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


