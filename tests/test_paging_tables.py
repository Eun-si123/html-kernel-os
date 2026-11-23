"""M3 private page-table C11 ABI safety and negative-oracle verification."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "native GCC required in CI")
class PrivatePagingTablesTests(unittest.TestCase):
    def test_supervisor_4k_mapping_and_reserved_slot_fail_closed(self):
        for optimize in ("-O0", "-O3"):
            with self.subTest(optimize=optimize):
                with tempfile.TemporaryDirectory(prefix="htmlk-paging-unit-") as tmp:
                    binary = Path(tmp) / "paging-oracle"
                    result = subprocess.run(
                        ["gcc", "-std=c11", optimize, "-march=x86-64",
                         "-Wall", "-Wextra", "-Werror",
                         "-fsanitize=undefined", "-fno-sanitize-recover=all",
                         "-I", str(ROOT / "boot"),
                         str(ROOT / "boot/paging_tables.c"),
                         str(ROOT / "tests/native/test_paging_tables.c"),
                         "-o", str(binary)],
                        capture_output=True, text=True, timeout=35,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    run = subprocess.run([str(binary)], capture_output=True,
                                         text=True, timeout=12)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(run.stdout,
                                     "M3 PRIVATE PAGE TABLE C11 CONTRACT PASS\n")
                    self.assertFalse(run.stderr)


if __name__ == "__main__":
    unittest.main()
