"""Preemptive interrupt stack layout contract at GCC -O0/-O3 with UBSan."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class M4PreemptFrameTests(unittest.TestCase):
    def test_x2apic_interrupt_frame_layout(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-preempt-frame-") as td:
            for optimization in ("-O0", "-O3"):
                with self.subTest(optimization=optimization):
                    binary = Path(td) / ("layout" + optimization)
                    subprocess.run([
                        "gcc", "-std=c11", optimization, "-Wall", "-Wextra",
                        "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I", str(ROOT / "boot"),
                        str(ROOT / "tests/native/test_preempt_frame.c"),
                        "-o", str(binary)], check=True, timeout=20)
                    result = subprocess.run([str(binary)], check=True,
                                            capture_output=True, text=True,
                                            timeout=10)
                    self.assertEqual(result.stdout,
                                     "M4 X2APIC FULL IRQ FRAME LAYOUT PASS\n")

if __name__ == "__main__":
    unittest.main()
