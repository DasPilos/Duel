import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.build_client_package as package_builder


class ClientPackageDisabledTests(unittest.TestCase):
    def test_building_the_python_client_package_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "client.zip"
            with self.assertRaises(RuntimeError) as raised:
                package_builder.build_client_package(destination)
            self.assertIn("отключена", str(raised.exception))
            self.assertFalse(destination.exists())

    def test_command_line_exits_with_code_2_and_message(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["build_client_package.py"]), \
                contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_info:
            package_builder.main()
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("отключена", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
