import sys
from PySide6.QtCore import QObject, Signal

class StreamToGui(QObject):
    text_written = Signal(str)

    def __init__(self, stream):
        super().__init__()
        self.stream = stream

    def write(self, text):
        self.stream.write(text)
        self.text_written.emit(text)

    def flush(self):
        self.stream.flush()

