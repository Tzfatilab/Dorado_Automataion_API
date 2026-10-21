"""Fatal analysis errors must terminate Rscript, without recursive log output."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class NanoTelFailureExitTests(unittest.TestCase):
    def test_warning_once_then_fatal_error_exits(self):
        rscript = shutil.which('Rscript')
        if not rscript:
            self.skipTest('Rscript is not installed')
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='nanotel-error-test-') as folder:
            script = Path(folder) / 'failure.R'
            script.write_text('''
if (!requireNamespace("logr", quietly=TRUE)) quit(status=77)
for (expression in parse("dorado_workflow/data/NanoTel.R")) {
  if (is.call(expression) && identical(expression[[1]], as.name("<-")) &&
      identical(expression[[2]], as.name("open_nanotel_log"))) eval(expression)
}
open_nanotel_log(file.path(tempdir(), "failure-test.log"))
stopifnot(is.null(getOption("error")), is.null(getOption("warning.expression")))
logr::log_print("Normal logging still works", console=FALSE)
warning("TEST_WARNING_ONCE")
stop("TEST_FATAL_WRITE_FAILURE")
''', encoding='utf-8')
            result = subprocess.run([rscript, str(script)], cwd=root,
                                    capture_output=True, text=True, timeout=20)
            if result.returncode == 77:
                self.skipTest('logr is not installed')
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertEqual(output.count('TEST_WARNING_ONCE'), 1, output)
            self.assertEqual(output.count('TEST_FATAL_WRITE_FAILURE'), 1, output)
            self.assertNotIn('Object cannot be printed to log', output)


if __name__ == '__main__':
    unittest.main()
