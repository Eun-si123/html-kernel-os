"""M5-E2 pure Ring3 IRQ frame validator under 2 UBSan optimization levels."""
from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TimeoutFrameTests(unittest.TestCase):
    def test_guard_native_ubsan_O0_O3(self) -> None:
        with tempfile.TemporaryDirectory(prefix='htmlk-timeout-guard-') as folder:
            for opt in ('-O0','-O3'):
                exe=Path(folder)/(opt+'.exe')
                subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',
                                '-fsanitize=undefined','-fno-sanitize-recover=undefined',opt,
                                '-I',str(ROOT/'boot'),
                                str(ROOT/'tests/native/test_user_timeout_frame.c'),
                                str(ROOT/'boot/user_timeout_frame.c'),'-o',str(exe)],
                               check=True,timeout=30)
                subprocess.run([str(exe)],check=True,timeout=12)

if __name__=='__main__':unittest.main()
