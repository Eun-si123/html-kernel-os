"""Host-independent M4 user page-table validation and negative cases."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class M4UserPages(unittest.TestCase):
    def test_user_mapping_permissions_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-user-pages-") as td:
            for opt in ("-O0", "-O3"):
                with self.subTest(optimization=opt):
                    exe = Path(td) / ("user-pages" + opt)
                    subprocess.run(["gcc", "-std=c11", opt, "-Wall",
                        "-Wextra", "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/user_pages.c"),
                        str(ROOT / "tests/native/test_user_pages.c"),
                        "-o", str(exe)], check=True, timeout=30)
                    run = subprocess.run([str(exe)], check=True,
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.stdout,
                        "M4 RING3 PAGES PERMISSIONS + NEGATIVE REJECTION PASS\n")

if __name__ == "__main__":
    unittest.main()
