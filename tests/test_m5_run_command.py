"""M5-D native command grammar is explicitly opt-in, with UBSan guards."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class M5InteractiveParserTests(unittest.TestCase):
    def test_host_run_parser_ubsan_o0_o3(self):
        with tempfile.TemporaryDirectory(prefix="m5-run-parser-") as root:
            for opt in ("-O0", "-O3"):
                exe = Path(root) / opt[1:]
                subprocess.run([
                    "gcc", "-std=c11", opt, "-DHTMLK_M5_INTERACTIVE_RUN",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "boot"),
                    str(ROOT / "boot/serial_command.c"),
                    str(ROOT / "boot/romfs.c"),
                    str(ROOT / "tests/native/test_m5_run_command.c"),
                    "-o", str(exe)
                ], check=True, timeout=30)
                result = subprocess.run([str(exe)], capture_output=True,
                                        text=True, check=True, timeout=10)
                self.assertEqual(result.stdout,
                                 "M5-D HOST RUN PARSER CANONICAL/INVALID PASS\n")


if __name__ == "__main__":
    unittest.main()
