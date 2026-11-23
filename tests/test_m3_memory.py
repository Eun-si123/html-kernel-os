"""M3 portable unit gate: compile and run the pure freestanding page-pool oracle."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "GCC unavailable; native CI is mandatory")
class MemoryBootstrapTests(unittest.TestCase):
    def test_page_pool_respects_reserved_ranges_and_exhaustion(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-m3-unit-") as td:
            output = Path(td) / "pool"
            built = subprocess.run(
                ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "boot"),
                 str(ROOT / "boot/page_pool.c"),
                 str(ROOT / "tests/native/test_page_pool.c"),
                 "-o", str(output)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            tested = subprocess.run(
                [str(output)], capture_output=True, text=True, timeout=10)
            self.assertEqual(tested.returncode, 0, tested.stderr)
            self.assertEqual(
                tested.stdout, "M3 PAGE POOL HOST CONTRACT PASS\n")
            self.assertFalse(tested.stderr)


if __name__ == "__main__":
    unittest.main()
