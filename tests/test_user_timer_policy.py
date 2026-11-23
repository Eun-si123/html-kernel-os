"""M4-D frame/selector ABI validator under independent GCC UBSan builds."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UserTimerFrame(unittest.TestCase):
    def test_irq_frame_rejections_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-d-frame-") as td:
            for opt in ("-O0", "-O3"):
                with self.subTest(optimization=opt):
                    exe = Path(td) / ("m4-d" + opt)
                    subprocess.run([
                        "gcc", "-std=c11", opt, "-Wall", "-Wextra",
                        "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I",
                        str(ROOT / "boot"),
                        str(ROOT / "boot/user_timer_policy.c"),
                        str(ROOT / "tests/native/test_user_timer_policy.c"),
                        "-o", str(exe)], check=True, timeout=30)
                    run = subprocess.run([str(exe)], check=True,
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.stdout,
                        "M4-D USER IRQ FRAME ABI NEGATIVE POLICY PASS\n")


if __name__ == "__main__":
    unittest.main()
