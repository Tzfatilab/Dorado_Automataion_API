import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gui.app_window import AppWindow
from PySide6.QtWidgets import QApplication

# PACKAGING TODO [PACKAGE-NAME]
# Keep this synchronized with the final distribution name in pyproject.toml.
DISTRIBUTION_NAME = "package-name-pending"


def _distribution_version():
    """Return the installed package version."""
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        # Allows the launcher to run directly from a source checkout.
        return "0.0.0"


def _build_parser():
    """Create the public GUI launcher argument parser."""
    parser = argparse.ArgumentParser(
        description="Launch the telomere analysis application."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_distribution_version()}",
    )
    return parser


def _show_initial_window(window, screen):
    """Open large displays restored and smaller displays maximized."""
    if screen is None:
        window.showMaximized()
        window._apply_screen_scaling()
        return

    available = screen.availableGeometry()
    is_large_screen = available.width() >= 2200 or available.height() >= 1200
    if not is_large_screen:
        window.showMaximized()
        window._apply_screen_scaling()
        return

    # This is the same window state produced by clicking the Restore square
    # beside the close button on a maximized window.
    window.showNormal()
    window._apply_screen_scaling()


def main(argv=None):
    """Launch the installed GUI application."""
    args = sys.argv[1:] if argv is None else argv
    _build_parser().parse_args(args)

    app = QApplication([sys.argv[0]])
    window = AppWindow()
    _show_initial_window(window, app.primaryScreen())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
