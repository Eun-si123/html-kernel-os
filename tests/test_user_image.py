"""M5-C1 bounded binary generator, relocation rejection and C header oracle."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.build_user_image import build, fnv1a, pack, MAX_CODE_BYTES

ROOT = Path(__file__).resolve().parents[1]


class UserImageTests(unittest.TestCase):
    def test_deterministic_embedded_program(self):
        with tempfile.TemporaryDirectory(prefix="hke-test-") as temp:
            out1, out2 = Path(temp)/"a.hke", Path(temp)/"b.hke"
            src = ROOT/"examples/user-programs/hello.S"
            first = build(src, out1)
            self.assertEqual(first, build(src, out2))
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            self.assertEqual(first[:8], b"HKEX\x01\x20\0\0")
            code = first[32:]
            self.assertEqual(int.from_bytes(first[12:16],"little"),len(code))
            self.assertEqual(int.from_bytes(first[16:20],"little"),fnv1a(code))
            self.assertLess(len(first), 4096)

    def test_reject_empty_oversize_and_relocations(self):
        with self.assertRaisesRegex(ValueError,"code length"):
            pack(b"")
        with self.assertRaisesRegex(ValueError,"code length"):
            pack(b"A"*(MAX_CODE_BYTES+1))
        with tempfile.TemporaryDirectory(prefix="hke-negative-") as temp:
            root=Path(temp)
            src=root/"has-relocation.S"
            src.write_text('.section .text\n.global entry\nentry:\ncall external_function\n')
            with self.assertRaisesRegex(ValueError,"relocation"):
                build(src,root/"should-not-exist.hke")
            self.assertFalse((root/"should-not-exist.hke").exists())
            src.write_bytes(b"A"*16385)
            with self.assertRaisesRegex(ValueError,"source size"):
                build(src,root/"large.hke")
            src.unlink()
            src.symlink_to(ROOT/"examples/user-programs/hello.S")
            with self.assertRaisesRegex(ValueError,"regular assembly"):
                build(src,root/"symlink.hke")

    def test_pure_c_header_oracle_ubsan(self):
        with tempfile.TemporaryDirectory(prefix="hke-c-") as temp:
            for opt in ("-O0","-O3"):
                executable = Path(temp)/f"loader-{opt}"
                subprocess.run(["gcc", "-std=c11", opt, "-fsanitize=undefined",
                                "-fno-sanitize-recover=all", "-Wall", "-Wextra",
                                "-Werror", "-I",str(ROOT/"boot"),
                                str(ROOT/"boot/user_image.c"),
                                str(ROOT/"tests/native/test_user_image.c"),
                                "-o",str(executable)],check=True,timeout=25)
                run = subprocess.run([str(executable)],text=True,capture_output=True,
                                     check=True,timeout=10)
                self.assertEqual(run.stdout,"M5 HKEX NATIVE HEADER/HASH/SIZE/NEGATIVES PASS\n")


if __name__ == '__main__':
    unittest.main()
