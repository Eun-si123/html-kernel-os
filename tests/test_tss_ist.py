"""M3 64-bit x86 TSS/IST descriptor C11 UBSan host oracle."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "GCC required by native kernel CI")
class TSSISTTests(unittest.TestCase):
    def test_descriptor_layout_canonical_ranges_and_stack_bounds(self):
        for optimize in ("-O0", "-O3"):
            with self.subTest(optimize=optimize):
                with tempfile.TemporaryDirectory(prefix="htmlk-tss-") as tmp:
                    binary = Path(tmp) / "tss-native"
                    build = subprocess.run(
                        ["gcc", "-std=c11", optimize, "-march=x86-64",
                         "-mgeneral-regs-only", "-mno-red-zone",
                         "-Wall", "-Wextra", "-Werror",
                         "-fsanitize=undefined", "-fno-sanitize-recover=all",
                         "-I", str(ROOT / "boot"),
                         str(ROOT / "boot/tss_ist.c"),
                         str(ROOT / "tests/native/test_tss_ist.c"),
                         "-o", str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(build.returncode, 0, build.stderr)
                    run = subprocess.run([str(binary)], capture_output=True,
                                         text=True, timeout=12)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(run.stdout,
                                     "M3 TSS/IST DESCRIPTOR HOST CONTRACT PASS\n")
                    self.assertFalse(run.stderr)


if __name__ == "__main__":
    unittest.main()
