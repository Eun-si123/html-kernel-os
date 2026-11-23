"""M3 real IDT descriptor constructor host oracle and compiler ISA checks."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "GCC required by native CI")
class ExceptionIDTTests(unittest.TestCase):
    def test_64bit_gate_binary_layout_and_canonical_handlers(self):
        for optimize in ("-O0", "-O3"):
            with self.subTest(optimize=optimize):
                with tempfile.TemporaryDirectory(prefix="htmlk-idt-") as temporary:
                    binary = Path(temporary) / "idt-host"
                    compile_result = subprocess.run(
                        ["gcc", "-std=c11", optimize, "-march=x86-64",
                         "-mgeneral-regs-only", "-mno-red-zone",
                         "-Wall", "-Wextra", "-Werror",
                         "-fsanitize=undefined", "-fno-sanitize-recover=all",
                         "-I", str(ROOT / "boot"),
                         str(ROOT / "boot/exception_idt.c"),
                         str(ROOT / "tests/native/test_exception_idt.c"),
                         "-o", str(binary)],
                        capture_output=True, text=True, timeout=35,
                    )
                    self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
                    run = subprocess.run([str(binary)], capture_output=True,
                                         text=True, timeout=10)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(run.stdout,
                                     "M3 IDT DESCRIPTOR NATIVE CONTRACT PASS\n")
                    self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
