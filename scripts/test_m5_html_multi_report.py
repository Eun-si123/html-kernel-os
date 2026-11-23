#!/usr/bin/env python3
"""M5-F3 real QEMU: bounded repeated HTML reports and guarded 9th syscall."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import CPU, SPIN_TRACE
from test_m5_html_user_text import build
from build_user_image import build as build_user_image

TEXT=b'M5_F2_USER_TEXT=tick\n'
NUMERIC=b'M5_C_USER_VALUE=2026\n'


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-f3-') as folder:
        work=Path(folder)
        cache=Path(os.getenv('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        kernel=ROOT/'examples/kernel.html'
        app=ROOT/'examples/user-programs/html-multireport.html'
        romfs=work/'romfs';shutil.copytree(ROOT/'examples/romfs',romfs)
        build_user_image(ROOT/'examples/user-programs/bad-report-budget.S',
                         romfs/'badbudget.hke')
        iso=work/'f3.iso';build(kernel,app,iso,work,cache,romfs)
        for trial in range(3):
            operations=[
                (b'run /apps/hello.hke\r',NUMERIC),
                (b'run /badbudget.hke\r',b'M5_ERR_USER_SYSCALL\n'),
                (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
                (b'run /apps/hello.hke\r',NUMERIC),
                (b'run /apps/spin.hke\r',SPIN_TRACE),
                (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
            ]
            log,uart=exercise(iso,operations,HTML,cpu=CPU)
            assert log.startswith(BASE) and log.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert log.count(TEXT)==4,(trial,log)
            assert log.count(NUMERIC)==2,(trial,log)
            assert log.count(b'M5_C_USER_VALUE=777\n')==8,(trial,log)
            assert log.count(b'M5_ERR_USER_SYSCALL\n')==1,(trial,log)
            assert log.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==1
            assert log.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==2
            assert log.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1
            assert uart.count(TEXT)==4 and uart.count(NUMERIC)==2
            assert uart.count(b'M5_C_USER_VALUE=777\n')==8
            assert uart.count(b'M5_ERR_USER_SYSCALL\n')==1
        print('M5-F3 REAL QEMU 3x TWO HTML MULTIREPORT APPS + 9TH SYSCALL ABORT + x2APIC PASS')
        edited=work/'changed-user.html';source=app.read_text()
        assert source.count('tick')==1 and source.count('2026')==1
        edited.write_text(source.replace('tick','tock').replace('2026','2027'))
        altered_iso=work/'altered-user.iso';build(kernel,edited,altered_iso,work,cache,romfs)
        edited_text=b'M5_F2_USER_TEXT=tock\n'
        edited_value=b'M5_C_USER_VALUE=2027\n'
        log,uart=exercise(altered_iso,[
            (b'run /apps/hello.hke\r',edited_value),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert altered_iso.read_bytes()!=iso.read_bytes()
        assert log.count(edited_text)==2 and edited_value in uart
        assert TEXT not in log and NUMERIC not in log
        print('M5-F3 USER HTML SOURCE MUTATION -> DIFFERENT ISO + REAL UART TEXT/NUMBER PASS')
        changed_kernel=work/'changed-kernel.html'
        previous=kernel.read_text();assert previous.count('Hello from HTML Kernel!')==1
        changed_kernel.write_text(previous.replace('Hello from HTML Kernel!',
                                                   'F3 ALTERNATE KERNEL BOOT!'))
        kernel_iso=work/'changed-kernel.iso'
        build(changed_kernel,app,kernel_iso,work,cache,romfs)
        changed_html=HTML.replace(b'Hello from HTML Kernel!',
                                  b'F3 ALTERNATE KERNEL BOOT!')
        log,_=exercise(kernel_iso,[
            (b'run /apps/hello.hke\r',NUMERIC),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+changed_html)],changed_html,cpu=CPU)
        assert kernel_iso.read_bytes()!=iso.read_bytes()
        assert log.endswith(b'M5_CONSOLE_EXIT\n'+changed_html)
        print('M5-F3 KERNEL HTML SOURCE MUTATION -> REAL NATIVE BOOT RESULT PASS')
        rejected=work/'too-many.html'
        rejected.write_text(source.replace('times="2"','times="8"'))
        invalid=work/'invalid.iso'
        command=[sys.executable,str(ROOT/'scripts/build_boot.py'),
                 '--source',str(kernel),'--user-app-html',str(rejected),
                 '--exception-idt','--tss-ist','--romfs-run-console',
                 '--user-fault-recover','--user-timeout',
                 '--out',str(invalid)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=40)
        assert result.returncode != 0 and not invalid.exists()
        assert 'budget exceeds 8' in result.stderr
        print('M5-F3 9-REPORT HTML SOURCE REJECTED BEFORE ISO OUTPUT')
    print('M5-F3 BOUNDED MULTI-OUTPUT HTML USER APP NATIVE ACCEPTANCE PASS')

if __name__=='__main__':main()
