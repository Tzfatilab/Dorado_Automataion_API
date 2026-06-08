import sys
from PySide6.QtCore import QObject, Signal

"""Utilities for forwarding console-like stream output into the Qt GUI."""


class StreamToGui(QObject):
    """Wrap a text stream and mirror writes through a Qt signal."""

    text_written = Signal(str)

    def __init__(self, stream):
        """Store the target stream to forward writes and flush calls."""
        super().__init__()
        self.stream = stream

    def write(self, text):
        """Write text to the underlying stream and emit it to the GUI."""
        self.stream.write(text)
        self.text_written.emit(text)

    def flush(self):
        """Flush the underlying stream to keep file-like behavior compatible."""
        self.stream.flush()

