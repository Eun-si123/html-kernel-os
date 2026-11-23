"""M4-D pure ring3 timer interrupt ABI and malformed-frame oracle."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Ring3PreemptionFrameTest(unittest.TestCase):
    def test_cpl3_irq_frame_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-d-frame-") as td:
            for opt in ("-O0", "-O3"):
                with self.subTest(opt=opt):
                    output = Path(td) / ("frame" + opt)
                    subprocess.run([
                        "gcc", "-std=c11", opt, "-Wall", "-Wextra",
                        "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/user_preempt_frame.c"),
                        str(ROOT / "tests/native/test_user_preempt_frame.c"),
                        "-o", str(output)], check=True, timeout=20)
                    result = subprocess.run([str(output)],
                                            capture_output=True, text=True,
                                            check=True, timeout=10)
                    self.assertEqual(result.stdout,
                                     "M4-D PURE IRQ FRAME GUARD PASS\n")

if __name__ == "__main__":
    unittest.main()
