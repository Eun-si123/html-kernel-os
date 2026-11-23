#!/usr/bin/env python3
"""M5-F2 actual QEMU copyin: valid HTML string and invalid CPL3 pointers."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise,BASE,HTML
from test_m5_user_timeout import CPU, TIMER,SPIN_TRACE
from build_user_image import build as build_user_image

TEXT=b'M5_F2_USER_TEXT=Hello from HTML user mode!\n'
TRACE=(b'M5_RUN_START /apps/hello.hke\nM5_C_ROMFS_PROGRAM_LOADED\n'
       b'M5_C_USER_PAGES_READY\n'+TIMER+
       b'M5_C_RING3_STACK_OK\n'+TEXT+
       b'M5_C_RING3_EXIT_OK\nM5_C_USER_FRAMES_RECLAIMED\n'
       b'M5_RUN_DONE\nM5_PROMPT> ')


def build(kernel:Path,app:Path,iso:Path,work:Path,cache:Path,root:Path)->None:
    cmd=[sys.executable,str(ROOT/'scripts/build_boot.py'),
         '--source',str(kernel),'--user-app-html',str(app),
         '--romfs-root',str(root),'--out',str(iso),
         '--work-dir',str(work),'--cache-dir',str(cache),
         '--exception-idt','--tss-ist','--romfs-run-console',
         '--user-fault-recover','--user-timeout','--test-exit']
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=150)
    assert result.returncode==0 and 'HKEX_HTML_USER_IMAGE_BYTES=' in result.stdout,(
        result.stdout,result.stderr)


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-text-') as folder:
        work=Path(folder)
        cache=Path(os.getenv('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        user=ROOT/'examples/user-programs/html-message.html'
        kernel=ROOT/'examples/kernel.html'
        root=work/'romfs';shutil.copytree(ROOT/'examples/romfs',root)
        for source,dest in (
            ('bad-text-pointer.S','badptr.hke'),
            ('bad-text-length.S','badlen.hke'),
            ('bad-text-control.S','badctrl.hke'),
        ):
            build_user_image(ROOT/'examples/user-programs'/source,root/dest)
        iso=work/'original.iso'
        build(kernel,user,iso,work,cache,root)
        for run in range(3):
            actions=[
                (b'run /apps/hello.hke\r',TRACE),
                (b'run /badptr.hke\r',b'M5_ERR_USER_SYSCALL\n'),
                (b'run /badlen.hke\r',b'M5_ERR_USER_SYSCALL\n'),
                (b'run /badctrl.hke\r',b'M5_ERR_USER_SYSCALL\n'),
                (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
                (b'run /apps/hello.hke\r',TRACE),
                (b'run /apps/spin.hke\r',SPIN_TRACE),
                (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
            ]
            log,uart=exercise(iso,actions,HTML,cpu=CPU)
            assert log.startswith(BASE) and log.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert log.count(TRACE)==2,(run,log)
            assert log.count(TEXT)==2
            assert log.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED')==3
            assert log.count(b'M5_ERR_USER_SYSCALL')==3
            assert log.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED')==1
            assert log.count(b'M5_C_USER_FRAMES_RECLAIMED')==2
            assert uart.count(TEXT)==2
            assert b'\x1b[' not in uart
        print('M5-F2 3x REAL QEMU: HTML TEXT COPYIN + 3 INVALID CPL3 POINTER/LENGTH/CONTROL -> SHELL + TIMER PASS')
        original=user.read_text()
        assert original.count('Hello from HTML user mode!')==1
        modified=work/'changed-app.html'
        modified.write_text(original.replace('Hello from HTML user mode!',
                                             'Changed native HTML user output!'))
        edited_iso=work/'changed-app.iso'
        build(kernel,modified,edited_iso,work,cache,root)
        changed_text=b'M5_F2_USER_TEXT=Changed native HTML user output!\n'
        changed_trace=TRACE.replace(TEXT,changed_text)
        log,uart=exercise(edited_iso,[
            (b'run /apps/hello.hke\r',changed_trace),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert edited_iso.read_bytes()!=iso.read_bytes()
        assert changed_text in uart and TEXT not in log
        print('M5-F2 MODIFIED TEXT HTML -> DIFFERENT ISO AND REAL USER-CODE UART BYTES')
        changed_kernel=work/'changed-kernel.html'
        k=kernel.read_text();assert k.count('Hello from HTML Kernel!')==1
        changed_kernel.write_text(k.replace('Hello from HTML Kernel!','F2 UPDATED KERNEL!'))
        kernel_iso=work/'changed-kernel.iso'
        build(changed_kernel,user,kernel_iso,work,cache,root)
        expected=HTML.replace(b'Hello from HTML Kernel!',b'F2 UPDATED KERNEL!')
        log,_=exercise(kernel_iso,[
            (b'run /apps/hello.hke\r',TRACE),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+expected)],expected,cpu=CPU)
        assert kernel_iso.read_bytes()!=iso.read_bytes()
        assert log.endswith(b'M5_CONSOLE_EXIT\n'+expected)
        print('M5-F2 CHANGED KERNEL HTML -> SEPARATE REAL BOOT RESULT')
    print('M5-F2 BOUNDED USER TEXT POINTER AND REAL CPL3 EXECUTION PROOF PASS')

if __name__=='__main__':main()
