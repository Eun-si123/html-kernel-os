"""M4 bounded task state transitions: host C compiler regression."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("gcc"), "host GCC required")
class M4TaskModelTests(unittest.TestCase):
    def test_state_transitions_negative_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-task-model-") as td:
            for optimization in ("-O0", "-O3"):
                with self.subTest(optimization=optimization):
                    binary = Path(td) / ("model" + optimization)
                    subprocess.run([
                        "gcc", "-std=c11", optimization,
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/task_model.c"),
                        str(ROOT / "tests/native/test_task_model.c"),
                        "-o", str(binary)], check=True, timeout=30)
                    run = subprocess.run([str(binary)], check=True,
                                         capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.stdout,
                                     "M4 MODEL TRANSITIONS + INVALID STATES PASS\n")

if __name__ == "__main__":
    unittest.main()
