"""Keep verification safe without mistaking instructional text for code."""
import contextlib
import io
import unittest
from verify import run_notebook


def notebook(source):
    return {'cells': [{'id': 'sample', 'cell_type': 'code', 'source': [source]}]}


class VerifierTests(unittest.TestCase):
    def test_instructional_string_is_not_a_flag_assignment(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            run_notebook(notebook("RUN_WEB = False\nprint('Set RUN_WEB = True to start.')"))
        self.assertIn('Executed 1 notebook code cells.', output.getvalue())

    def test_enabled_server_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'RUN_WEB = False'):
            run_notebook(notebook('RUN_WEB = True'))

    def test_computed_flag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'RUN_PRIVATE_DEMO = False'):
            run_notebook(notebook('RUN_PRIVATE_DEMO = bool(1)'))


if __name__ == '__main__':
    unittest.main()
