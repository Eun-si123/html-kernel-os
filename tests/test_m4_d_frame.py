"""Independent native frame architecture and invalid-state UBSan gates."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class M4DFrameTests(unittest.TestCase):
    def test_saved_cpl3_irq_context_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-d-frame-") as td:
            for opt in ("-O0", "-O3"):
                with self.subTest(optimization=opt):
                    exe = Path(td) / ("frame" + opt)
                    subprocess.run(["gcc", "-std=c11", opt,
                        "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/preempt_user_frame.c"),
                        str(ROOT / "tests/native/test_m4_d_frame.c"),
                        "-o", str(exe)], check=True, timeout=30)
                    run = subprocess.run([str(exe)], check=True,
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.stdout,
                        "M4-D CPL3 SAVED IRQ FRAME AND NEGATIVE STATES PASS\n")

if __name__ == "__main__":
    unittest.main()
