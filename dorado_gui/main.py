import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gui.app_window import AppWindow
from PySide6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AppWindow()
    #w.showMaximized()
    w.show()
    sys.exit(app.exec())