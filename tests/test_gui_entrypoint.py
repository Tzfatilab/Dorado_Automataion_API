import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from dorado_gui import main as gui_main


class GuiEntrypointTests(unittest.TestCase):
    @patch.object(gui_main, "AppWindow")
    @patch.object(gui_main, "QApplication")
    @patch.object(gui_main, "_show_initial_window")
    def test_main_launches_existing_window(self, show_window, application, app_window):
        application.return_value.exec.return_value = 0

        result = gui_main.main([])

        application.assert_called_once()
        app_window.assert_called_once_with()
        show_window.assert_called_once_with(
            app_window.return_value,
            application.return_value.primaryScreen.return_value,
        )
        application.return_value.exec.assert_called_once_with()
        self.assertEqual(result, 0)

    @patch.object(gui_main, "QApplication")
    def test_help_does_not_start_gui(self, application):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            gui_main.main(["--help"])

        self.assertEqual(result.exception.code, 0)
        self.assertIn("Launch the telomere analysis application", output.getvalue())
        application.assert_not_called()

    @patch.object(gui_main, "_distribution_version", return_value="0.0.0")
    @patch.object(gui_main, "QApplication")
    def test_version_does_not_start_gui(self, application, _version):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            gui_main.main(["--version"])

        self.assertEqual(result.exception.code, 0)
        self.assertIn("0.0.0", output.getvalue())
        application.assert_not_called()


if __name__ == "__main__":
    unittest.main()
