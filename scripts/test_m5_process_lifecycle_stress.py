#!/usr/bin/env python3
"""M5-E3: interleave real Ring3 program exits, syscalls, CPU faults and IRQ timeouts.

This is a single-vCPU QEMU regression, not a multi-process stress/sandbox claim.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import build, GOOD_TRACE, SPIN_TRACE, CPU
from build_user_image import build as build_user_image


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3-') as tmp:
        work=Path(tmp)
        romfs=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',romfs)
        build_user_image(ROOT/'examples/user-programs/bad-syscall.S',
                         romfs/'bad-id.hke')
        build_user_image(ROOT/'examples/user-programs/bad-argument.S',
                         romfs/'bad-argument.hke')
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        iso=work/'lifecycle.iso'
        build(ROOT/'examples/kernel.html',iso,work,cache,
              '--romfs-root',str(romfs))
        cmds=[
            (b'help\r', b'M5_HELP help ls cat /path run /path exit'),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /bad-id.hke\r',b'M5_ERR_USER_SYSCALL'),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /apps/spin.hke\r',SPIN_TRACE),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /apps/fault-io.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /bad-argument.hke\r',b'M5_ERR_USER_SYSCALL'),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /apps/fault-pf.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/fault-ro.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/spin.hke\r',SPIN_TRACE),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'run /apps/fault-ud.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'cat /welcome.txt\r',b'M5_CAT_END'),
            (b'run /wrong.hke\r',b'M5_ERR_NOT_FOUND'),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
        ]
        for boot in range(3):
            transcript,uart=exercise(iso,cmds,HTML,cpu=CPU)
            assert transcript.startswith(BASE) and transcript.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert transcript.count(GOOD_TRACE)==7,(boot,transcript)
            assert transcript.count(SPIN_TRACE)==2,(boot,transcript)
            assert transcript.count(b'M5_E2_REAL_USER_IRQ_LIMIT')==2,(boot,transcript)
            assert transcript.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED')==2,(boot,transcript)
            assert transcript.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED')==2,(boot,transcript)
            assert transcript.count(b'M5_E_FAULT_FRAMES_RECLAIMED')==4,(boot,transcript)
            assert transcript.count(b'M5_C_USER_FRAMES_RECLAIMED')==7,(boot,transcript)
            assert transcript.count(b'M5_ERR_USER_SYSCALL')==2,(boot,transcript)
            assert transcript.count(b'M5_ERR_USER_TIMEOUT')==2,(boot,transcript)
            assert transcript.count(b'M5_ERR_USER_FAULT')==4,(boot,transcript)
            assert transcript.count(b'M5_RUN_DONE')==7,(boot,transcript)
            assert b'M4_UNKNOWN_SYSCALL_REJECTED' not in transcript
            assert b'M5_CONSOLE_FATAL' not in transcript
            assert b'M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT' not in transcript
            assert uart.count(b'M5_ERR_USER_SYSCALL')==2,(boot,uart)
            assert uart.count(b'M5_ERR_USER_TIMEOUT')==2,(boot,uart)
            assert uart.count(b'M5_C_USER_VALUE=2026')==7,(boot,uart)
            assert uart.count(b'M5_ERR_USER_FAULT')==4,(boot,uart)
            print(f'M5-E3 INTERLEAVED QEMU BOOT {boot+1}/3: 7 OK + 2 TIMEOUT + 4 CPU FAULT + 2 SYSCALL ERR + 1 MISSING + EXIT PASS',flush=True)
    print('M5-E3 ACTUAL CPU MIXED RING3 LIFECYCLE/OWNER REUSE 3x ACCEPTANCE PASS')

if __name__=='__main__': main()
