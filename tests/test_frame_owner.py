"""M3 freestanding owner-tagged frame allocation C11 UBSan boundary oracle."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "native C compiler required in CI")
class FrameOwnerTests(unittest.TestCase):
    def test_owned_frame_reuse_exhaustion_and_double_free(self):
        for optimize in ("-O0", "-O3"):
            with self.subTest(optimize=optimize):
                with tempfile.TemporaryDirectory(prefix="htmlk-owner-") as work:
                    binary = Path(work) / "frame-owner"
                    proc = subprocess.run([
                        "gcc", "-std=c11", optimize, "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/page_pool.c"),
                        str(ROOT / "boot/frame_owner.c"),
                        str(ROOT / "tests/native/test_frame_owner.c"),
                        "-o", str(binary)],
                        capture_output=True, text=True, timeout=35)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    run = subprocess.run([str(binary)], capture_output=True,
                                         text=True, timeout=10)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(
                        run.stdout, "M3 FRAME OWNERSHIP / REUSE / EXHAUSTION PASS\n")
                    self.assertFalse(run.stderr)


if __name__ == "__main__":
    unittest.main()
