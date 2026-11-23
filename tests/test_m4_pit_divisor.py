"""Host compile oracle for bounded legacy PIT rate converter."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class M4PitDivisorTests(unittest.TestCase):
    def test_pit_rate_boundaries_ubsan_o0_o3(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-m4-pit-") as td:
            for level in ("-O0", "-O3"):
                with self.subTest(level=level):
                    binary = Path(td) / ("pit" + level)
                    subprocess.run([
                        "gcc", "-std=c11", level, "-mgeneral-regs-only",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/timer_irq.c"),
                        str(ROOT / "tests/native/test_pit_divisor.c"),
                        "-o", str(binary)], check=True, timeout=30)
                    result = subprocess.run([str(binary)], capture_output=True,
                                            text=True, check=True, timeout=10)
                    self.assertEqual(result.stdout, "M4 PIT RATE VALIDATION PASS\n")

if __name__ == "__main__":
    unittest.main()
