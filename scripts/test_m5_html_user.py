#!/usr/bin/env python3
"""M5-F1: real QEMU executes HTML-derived separate HKEX Ring3 code via UART."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import CPU, GOOD_TRACE, SPIN_TRACE


def build(kernel_html:Path, app_html:Path, iso:Path, work:Path,cache:Path)->None:
    cmd=[sys.executable,str(ROOT/'scripts/build_boot.py'),
         '--source',str(kernel_html),'--user-app-html',str(app_html),
         '--out',str(iso),'--work-dir',str(work),'--cache-dir',str(cache),
         '--exception-idt','--tss-ist','--romfs-run-console',
         '--user-fault-recover','--user-timeout','--test-exit']
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=150)
    assert result.returncode==0 and 'HKEX_HTML_USER_IMAGE_BYTES=' in result.stdout,(
        result.stdout,result.stderr)
    assert 'ROMFS_CONTENT_SHA256=' in result.stdout


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-html-user-') as tmp:
        work=Path(tmp)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        source=ROOT/'examples/kernel.html'
        app=ROOT/'examples/user-programs/html-hello.html'
        iso=work/'html-user.iso'
        build(source,app,iso,work,cache)
        for trial in range(3):
            events=[(b'run /apps/hello.hke\r',GOOD_TRACE),
                    (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
                    (b'run /apps/spin.hke\r',SPIN_TRACE),
                    (b'run /apps/hello.hke\r',GOOD_TRACE),
                    (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)]
            log,uart=exercise(iso,events,HTML,cpu=CPU)
            assert log.startswith(BASE)
            assert log.count(GOOD_TRACE)==2,(trial,log)
            assert log.count(SPIN_TRACE)==1,(trial,log)
            assert log.count(b'M5_C_USER_FRAMES_RECLAIMED')==2
            assert log.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED')==1
            assert uart.count(b'M5_C_USER_VALUE=2026')==2
        print('M5-F1 3x REAL QEMU HTML->HKEX->CPL3->INT80 UART, RERUN+TIMER PASS')
        altered=work/'app-updated.html'
        original=app.read_text()
        assert original.count('1046')==1
        altered.write_text(original.replace('1046','1045'))
        changed_iso=work/'html-app-changed.iso'
        build(source,altered,changed_iso,work,cache)
        expected=GOOD_TRACE.replace(b'M5_C_USER_VALUE=2026',b'M5_C_USER_VALUE=2027')
        log,uart=exercise(changed_iso,[
            (b'run /apps/hello.hke\r',expected),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert iso.read_bytes()!=changed_iso.read_bytes()
        assert b'M5_C_USER_VALUE=2027' in uart and b'M5_C_USER_VALUE=2026' not in log
        print('M5-F1 MODIFIED HTML USER SOURCE -> DIFFERENT ISO -> ACTUAL CPL3 VALUE 2027')
        changed_kernel=work/'kernel-updated.html'
        original_kernel=source.read_text()
        assert original_kernel.count('Hello from HTML Kernel!')==1
        changed_kernel.write_text(original_kernel.replace('Hello from HTML Kernel!',
                                                          'HTML-USER KERNEL UPDATED!'))
        changed_kernel_iso=work/'kernel-changed.iso'
        build(changed_kernel,app,changed_kernel_iso,work,cache)
        expected_kernel=HTML.replace(b'Hello from HTML Kernel!',b'HTML-USER KERNEL UPDATED!')
        log,_=exercise(changed_kernel_iso,[
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+expected_kernel)],expected_kernel,cpu=CPU)
        assert changed_kernel_iso.read_bytes()!=iso.read_bytes()
        assert log.endswith(b'M5_CONSOLE_EXIT\n'+expected_kernel)
        print('M5-F1 MUTATED HTML KERNEL SOURCE -> DIFFERENT ISO -> REAL NATIVE OUTPUT')
        for flags in (
            ('--user-app-html',str(app)),
            ('--romfs-run-console','--user-app-html',str(app)),
            ('--user-loader-probe','--user-app-html',str(app)),
            ('--exception-idt','--tss-ist','--romfs-run-console',
             '--user-app-html',str(app),'--user-app-source',
             str(ROOT/'examples/user-programs/hello.S')),
        ):
            out=work/'should-not-exist.iso'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/build_boot.py'),
                                   '--out',str(out),*flags],capture_output=True,
                                  text=True,timeout=20)
            assert result.returncode != 0 and not out.exists(),(flags,result.stderr)
        print('M5-F1 INCOMPATIBLE BUILD OPTIONS FAIL BEFORE CREATING ISO')
    print('M5-F1 TRUE HTML USER PROGRAM BOOT/EXECUTION PROOF PASS')


if __name__=='__main__':main()
