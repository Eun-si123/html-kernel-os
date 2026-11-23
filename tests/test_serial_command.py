"""M5-B host-side C parser sanitizers; native QEMU UART proof is separate."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SerialCommandNativeTests(unittest.TestCase):
    def test_native_parser_negative_bounds_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-serial-unit-") as temp:
            for optimization in ("-O0", "-O3"):
                executable = Path(temp) / f"serial-{optimization}"
                subprocess.run([
                    "gcc", "-std=c11", optimization, "-fsanitize=undefined",
                    "-fno-sanitize-recover=all", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "boot"), str(ROOT / "boot/serial_command.c"),
                    str(ROOT / "boot/romfs.c"),
                    str(ROOT / "tests/native/test_serial_command.c"),
                    "-o", str(executable),
                ], check=True, timeout=25)
                result = subprocess.run([str(executable)], check=True, text=True,
                                        capture_output=True, timeout=10)
                self.assertEqual(result.stdout, "M5 SERIAL PARSER HOST BOUNDS/RECOVERY PASS\n")


if __name__ == "__main__":
    unittest.main()
