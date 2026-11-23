#!/usr/bin/env python3
"""M5-F4 real BIOS QEMU: bounded HTML <halt code> reported after CPL3 exit."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from test_boot import ROOT, boot
from test_m5_html_user_text import build as build_iso, TEXT
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import CPU, SPIN_TRACE
from test_m5_user_loader import make_iso as build_legacy
from build_user_image import build as build_asm

BASE_USER=ROOT/'examples/user-programs/html-message.html'


def expect_completed(iso:Path,code:int,*,full:bool=False)->None:
    status=b'M5_RUN_DONE\n' if code==0 else f'M5_RUN_EXIT_CODE={code}\n'.encode()
    actions=[(b'run /apps/hello.hke\r',status)]
    if full:
        actions += [
            (b'run /badexit.hke\r',b'M5_ERR_USER_SYSCALL'),
            (b'run /exit7.hke\r',b'M5_RUN_EXIT_CODE=7\n'),
            (b'run /apps/fault-ud.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/spin.hke\r',b'M5_ERR_USER_TIMEOUT'),
            (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
            (b'run /apps/hello.hke\r',status),
        ]
    else:
        actions.append((b'run /apps/hello.hke\r',status))
    actions.append((b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML))
    trace,uart=exercise(iso,actions,HTML,cpu=CPU)
    assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
    assert trace.count(status)==(3 if full and code==7 else 2),(code,trace)
    assert uart.count(status)==(3 if full and code==7 else 2),(code,uart)
    assert trace.count(TEXT)==2,(code,trace)
    assert uart.count(TEXT)==2,(code,uart)
    if code==0:
        assert b'M5_RUN_EXIT_CODE=' not in trace,(code,trace)
    elif code==255:
        assert b'M5_RUN_DONE' not in trace,(code,trace)
    if full:
        assert trace.count(b'M5_RUN_EXIT_CODE=7\n')==3,(code,trace)
        assert trace.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==1,trace
        assert trace.count(b'M5_E_FAULT_FRAMES_RECLAIMED\n')==1,trace
        assert trace.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,trace
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==3,trace
        assert trace.count(b'M5_ERR_USER_SYSCALL')==1,trace
        assert b'M4_BAD_RING3_SYSCALL_FRAME' not in trace
        assert b'M5_E_USER_EOF_SYSCALL_REJECTED' not in trace
    else:
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==2,trace


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-f4-') as tmp:
        work=Path(tmp)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        root=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',root)
        for name,source in (
            ('badexit.hke','bad-exit-code.S'),
            ('exit7.hke','exit-seven-eof.S')):
            build_asm(ROOT/'examples/user-programs'/source,root/name)
        source=BASE_USER.read_text()
        assert source.count('<halt/>')==1
        images:dict[int,Path]={}
        for code in (0,7,255):
            app=work/f'html-exit-{code}.html'
            app.write_text(source.replace('<halt/>',f'<halt code="{code}"/>'))
            iso=work/f'html-exit-{code}.iso'
            build_iso(ROOT/'examples/kernel.html',app,iso,work,cache,root)
            images[code]=iso
        assert len({image.read_bytes() for image in images.values()})==3
        for attempt in range(3):
            expect_completed(images[7],7,full=True)
            print(f'M5-F4 REAL QEMU {attempt+1}/3: 7 STATUS, INVALID 256, EOF7, CPU FAULT, IRQ TIMEOUT, RERUN PASS',flush=True)
        expect_completed(images[0],0)
        expect_completed(images[255],255)
        print('M5-F4 DISTINCT HTML EXIT 0/7/255: DISTINCT ISOS AND ACTUAL UART STATUS PASS',flush=True)
        bad=work/'html-exit-256.html'
        bad.write_text(source.replace('<halt/>','<halt code="256"/>'))
        denied=work/'denied.iso'
        cmd=[sys.executable,str(ROOT/'scripts/build_boot.py'),
             '--source',str(ROOT/'examples/kernel.html'),
             '--user-app-html',str(bad),
             '--exception-idt','--tss-ist','--romfs-run-console',
             '--user-fault-recover','--user-timeout',
             '--out',str(denied)]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
        assert result.returncode!=0 and not denied.exists(),result.stderr
        assert 'halt code' in result.stderr,result.stderr
        print('M5-F4 INVALID HTML EXIT >255 DENIED BEFORE ISO OUTPUT',flush=True)
        legacy=work/'legacy-exit7.iso'
        build_legacy(ROOT/'examples/kernel.html',legacy,work,cache,
                     '--user-app-source',str(ROOT/'examples/user-programs/exit-seven-eof.S'))
        legacy_code,legacy_trace=boot(legacy,timeout=18)
        assert legacy_code==53,(legacy_code,legacy_trace)
        assert 'M4_BAD_RING3_SYSCALL_FRAME' in legacy_trace,legacy_trace
        assert 'M5_RUN_EXIT_CODE=' not in legacy_trace
        print('M5-F4 LEGACY STANDALONE CPL3 RDI7 STILL DENIED; NO GLOBAL ABI BROADENING',flush=True)
    print('M5-F4 NATIVE HTML USER EXIT STATUS REAL CPU ACCEPTANCE PASS')

if __name__=='__main__':main()
