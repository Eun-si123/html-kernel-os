"""M5-E3-C native UBSan guard; malformed user pointers are never dereferenced."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class UserSyscallPolicyTests(unittest.TestCase):
    def test_malformed_user_frame_owner_guard_ubsan_O0_O3(self):
        with tempfile.TemporaryDirectory(prefix='htmlk-user-int80-') as folder:
            for level in ('-O0','-O3'):
                output=Path(folder)/(level+'.exe')
                subprocess.run(['gcc','-std=c11',level,'-fsanitize=undefined',
                    '-fno-sanitize-recover=undefined','-Wall','-Wextra','-Werror',
                    '-I',str(ROOT/'boot'),str(ROOT/'boot/user_syscall_policy.c'),
                    str(ROOT/'tests/native/test_user_syscall_policy.c'),
                    '-o',str(output)],check=True,timeout=25)
                result=subprocess.run([str(output)],capture_output=True,text=True,
                                      check=True,timeout=10)
                self.assertIn('ORIGIN/OWNERSHIP GUARD PASS',result.stdout)

if __name__=='__main__':unittest.main()
