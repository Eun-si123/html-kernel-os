"""M5-F2 native UBSan rejection of user-pointer range/length boundaries."""
from __future__ import annotations
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class UserTextPolicyTests(unittest.TestCase):
    def test_native_ubsan_o0_o3_address_guards(self):
        with tempfile.TemporaryDirectory(prefix='htmlk-usertext-policy-') as tmp:
            for opt in (0,3):
                exe=Path(tmp)/f'policy-{opt}'
                subprocess.run(['gcc','-std=c11',f'-O{opt}',
                    '-fsanitize=undefined','-fno-sanitize-recover=all',
                    '-Wall','-Wextra','-Werror','-I',str(ROOT/'boot'),
                    str(ROOT/'boot/user_text_policy.c'),
                    str(ROOT/'tests/native/test_user_text_policy.c'),
                    '-o',str(exe)],check=True,capture_output=True,timeout=25)
                subprocess.run([str(exe)],check=True,capture_output=True,timeout=10)

if __name__=='__main__':unittest.main()
