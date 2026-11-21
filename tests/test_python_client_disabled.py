import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# Точки входа Python-клиента и Python-редактора. Код остаётся архивом, запуск отключён.
ENTRY_COMMANDS = (
    ["main.py"],
    ["map_editor.py"],
    ["-m", "deck.editor"],
)


class PythonClientDisabledTests(unittest.TestCase):
    def test_entry_points_refuse_to_start_and_point_to_godot(self):
        for command in ENTRY_COMMANDS:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=PROJECT,
                    capture_output=True,
                    timeout=60,
                    env={"PYTHONUTF8": "1", "PATH": "", "SYSTEMROOT": ""},
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("godot_client", result.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
