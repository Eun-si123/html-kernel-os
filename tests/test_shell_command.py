"""Host-native M5-D run command grammar with UBSan at two optimization levels."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class ShellParserTests(unittest.TestCase):
    def test_m5_d_parser_command_bounds(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-m5-d-parser-") as temp:
            for opt in ("-O0", "-O3"):
                out=Path(temp)/f"shell{opt}"
                subprocess.run(["gcc","-std=c11",opt,"-DHTMLK_M5_D_SHELL",
                                "-fsanitize=undefined","-fno-sanitize-recover=all",
                                "-Wall","-Wextra","-Werror","-I",str(ROOT/"boot"),
                                str(ROOT/"boot/serial_command.c"),
                                str(ROOT/"boot/romfs.c"),
                                str(ROOT/"tests/native/test_shell_command.c"),
                                "-o",str(out)],check=True,timeout=25)
                actual=subprocess.run([str(out)],capture_output=True,text=True,
                                      check=True,timeout=10)
                self.assertEqual(actual.stdout,"M5-D SHELL PARSER / PATH / LONG LINE PASS\n")

if __name__ == "__main__":
    unittest.main()
