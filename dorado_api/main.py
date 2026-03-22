import sys
from pathlib import Path

# Add parent directory to path so dorado_workflow is importable
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (QApplication)
from app_window import AppWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AppWindow()
    w.showMaximized()
    w.show()
    sys.exit(app.exec())