"""M3 framebuffer codegen contracts and host-native pixel writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from compiler.htmlk import compile_html

ROOT = Path(__file__).resolve().parents[1]


class FramebufferContractTests(unittest.TestCase):
    def test_serial_mirrors_to_framebuffer_only_under_native_opt_in(self):
        sample = '<kernel><onboot><print>HELLO</print><halt/></onboot></kernel>'
        kernel = compile_html(sample, target="kernel")
        linux = compile_html(sample, target="linux")
        self.assertIn("#ifdef HTMLK_FB_CONSOLE", kernel)
        self.assertIn("htmlk_fb_putchar(v)", kernel)
        self.assertIn("#ifdef HTMLK_FB_TEST", kernel)
        self.assertIn("htmlk_fb_verify_probe();", kernel)
        self.assertNotIn("htmlk_fb_putchar", linux)
        self.assertNotIn("htmlk_fb_verify_probe", linux)

    @unittest.skipUnless(shutil.which("gcc"), "GCC required for native pixel verification")
    def test_real_memory_pixels_and_malformed_framebuffer_modes(self):
        for optimization in ("-O0", "-O3"):
            with self.subTest(optimization=optimization):
                with tempfile.TemporaryDirectory(prefix="htmlk-video-") as folder:
                    binary = Path(folder) / "native-video"
                    built = subprocess.run([
                        "gcc", "-std=c11", optimization, "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/console_fb.c"),
                        str(ROOT / "tests/native/test_console_fb.c"),
                        "-o", str(binary),
                    ], capture_output=True, text=True, timeout=40)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    run = subprocess.run([str(binary)], capture_output=True,
                                         text=True, timeout=15)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(
                        run.stdout, "M3 NATIVE FRAMEBUFFER GLYPH AND BOUNDS PASS\n")
                    self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
