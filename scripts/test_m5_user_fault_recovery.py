#!/usr/bin/env python3
"""M5-E1 real x86-64 CPU user fault -> frame reclaim -> live COM1 prompt."""
from __future__ import annotations
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from test_boot import ROOT, SUCCESS_EXIT
from test_m5_interactive_run import exercise, APP_TRACE, BASE, HTML

FAULTS=(
 (b"run /apps/fault-io.hke\r", b"M5_E_USER_GP_0\n"),
 (b"run /apps/fault-pf.hke\r", b"M5_E_USER_PF_5\n"),
 (b"run /apps/fault-ro.hke\r", b"M5_E_USER_PF_7\n"),
 (b"run /apps/fault-ud.hke\r", b"M5_E_USER_UD\n"),
)

def build(source:Path,iso:Path,work:Path,cache:Path,*extra:str)->None:
    result=subprocess.run([
        sys.executable,str(ROOT/'scripts/build_boot.py'),
        '--source',str(source),'--out',str(iso),
        '--cache-dir',str(cache),'--work-dir',str(work),
        '--exception-idt','--tss-ist','--romfs-run-console',
        '--user-fault-recover','--test-exit',*extra],
        cwd=ROOT,capture_output=True,text=True,timeout=180)
    if result.returncode:
        raise AssertionError(f'M5-E1 build failed:\n{result.stdout}\n{result.stderr}')
    assert 'ROMFS_CONTENT_SHA256=' in result.stdout,result.stdout

def recover_invalid_syscall_and_reexecute(work: Path, cache: Path,
                                         source: Path, app_source: Path,
                                         label: str) -> None:
    """Bad Ring3 syscall must retire only that task, not the UART shell."""
    from build_user_image import build as build_user_image
    image_root = work / ('romfs-' + label)
    shutil.copytree(ROOT / 'examples/romfs', image_root)
    build_user_image(ROOT / 'examples/user-programs/hello.S',
                     image_root / 'good.hke')
    iso = work / (label + '-syscall.iso')
    build(source, iso, work, cache, '--romfs-root',str(image_root),
          '--user-app-source',str(app_source))
    good_trace = APP_TRACE.replace(b'/apps/hello.hke',b'/good.hke')
    trace, uart = exercise(iso,[
        (b'run /good.hke\r',good_trace),
        (b'run /apps/hello.hke\r',b'M5_ERR_USER_SYSCALL'),
        (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
        (b'run /good.hke\r',good_trace),
        (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML)
    assert trace.count(b'M5_E_USER_BAD_SYSCALL\n')==1,trace
    assert trace.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==1,trace
    assert trace.count(b'M5_ERR_USER_SYSCALL\n')==1,trace
    assert trace.count(b'M5_RUN_DONE\n')==2,trace
    assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==2,trace
    assert trace.count(b'M5_C_USER_VALUE=2026\n')==2,trace
    assert uart.count(b'M5_ERR_USER_SYSCALL\n')==1,uart
    assert uart.count(b'M5_C_USER_VALUE=2026')==2,uart
    assert b'M4_UNKNOWN_SYSCALL_REJECTED' not in trace,trace


def main():
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-e1-') as temp:
        work=Path(temp)
        cache=Path(os.getenv('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        source=ROOT/'examples/kernel.html'
        original=work/'e1.iso'
        build(source,original,work,cache)
        for repeat in range(3):
            commands=[(b'help\r',b'M5_HELP help ls cat /path run /path exit'),
                      (b'cat /welcome.txt\r',b'M5_CAT_END')]
            for command,expected in FAULTS:
                commands.append((command,b'M5_ERR_USER_FAULT'))
                commands.append((b'run /apps/hello.hke\r',APP_TRACE))
            commands.append((b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML))
            transcript,uart=exercise(original,commands,HTML)
            assert transcript.startswith(BASE)
            assert transcript.count(b'M5_ERR_USER_FAULT')==4
            assert transcript.count(b'M5_E_FAULT_FRAMES_RECLAIMED')==4
            assert transcript.count(b'M5_C_USER_FRAMES_RECLAIMED')==4
            assert transcript.count(APP_TRACE)==4
            assert transcript.count(b'M5_RUN_DONE')==4
            assert transcript.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            for _,expected in FAULTS:
                assert transcript.count(expected)==1,(expected,transcript)
            assert b'M3_IST_PF_STACK_BAD' not in transcript
            assert transcript.count(b'M3_IST_PF_STACK_OK')==2
            assert uart.count(b'M5_ERR_USER_FAULT')==4
            assert uart.count(b'M5_C_USER_VALUE=2026')==4
        print('M5-E1 REAL QEMU 3x: #GP/#PF5/#PF7/#UD -> CLEANUP -> RE-RUN CPL3 PASS')
        trace,_=exercise(original,[],HTML,idle=True)
        assert trace==BASE
        print('M5-E1 IDLE: NO UART INPUT -> NO USER EXECUTION')

        edited_html=work/'changed.html'
        original_html=source.read_text()
        assert original_html.count('Hello from HTML Kernel!')==1
        edited_html.write_text(original_html.replace('Hello from HTML Kernel!',
                                                    'M5-E1 CHANGED HTML!'))
        html_iso=work/'changed-html.iso'
        build(edited_html,html_iso,work,cache)
        expected_html=HTML.replace(b'Hello from HTML Kernel!',b'M5-E1 CHANGED HTML!')
        trace,_=exercise(html_iso,[
            (b'run /apps/fault-ud.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/hello.hke\r',APP_TRACE),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+expected_html)],expected_html)
        assert html_iso.read_bytes()!=original.read_bytes()
        assert trace.endswith(b'M5_CONSOLE_EXIT\n'+expected_html)
        assert HTML not in trace
        print('M5-E1 MUTATED HTML SOURCE CHANGES NATIVE ISO AND REAL GUEST OUTPUT')

        changed_app=work/'modified.S'
        asm=(ROOT/'examples/user-programs/hello.S').read_text()
        assert asm.count('$2026')==1
        changed_app.write_text(asm.replace('$2026','$2027'))
        app_iso=work/'changed-user.iso'
        build(source,app_iso,work,cache,'--user-app-source',str(changed_app))
        changed_trace=APP_TRACE.replace(b'M5_C_USER_VALUE=2026',b'M5_C_USER_VALUE=2027')
        trace,uart=exercise(app_iso,[
            (b'run /apps/fault-pf.hke\r',b'M5_ERR_USER_FAULT'),
            (b'run /apps/hello.hke\r',changed_trace),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML)
        assert app_iso.read_bytes()!=original.read_bytes()
        assert b'M5_C_USER_VALUE=2026' not in trace
        assert b'M5_C_USER_VALUE=2027' in uart
        print('M5-E1 MUTATED USER IMAGE CHANGES REAL CPL3 SYSCALL OUTPUT')

        recover_invalid_syscall_and_reexecute(work,cache,source,
            ROOT/'examples/user-programs/bad-syscall.S','invalid-id')
        recover_invalid_syscall_and_reexecute(work,cache,source,
            ROOT/'examples/user-programs/bad-argument.S','invalid-argument')
        print('M5-E1 INVALID SYSCALL ID/ARG: USER RETIRED, LIVE SHELL AND RE-RUN PASS')

        for opts in (('--user-fault-recover',),
                     ('--user-fault-recover','--exception-idt','--tss-ist'),
                     ('--user-fault-recover','--romfs-run-console'),
                     ('--user-fault-recover','--romfs-run-console',
                      '--exception-idt','--tss-ist','--romfs-console'),
                     ('--user-fault-recover','--romfs-run-console',
                      '--exception-idt','--tss-ist','--user-preempt-probe')):
            target=work/'invalid.iso'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/build_boot.py'),
                                   '--out',str(target),*opts],
                                  capture_output=True,text=True,timeout=15)
            assert result.returncode!=0 and not target.exists(),(opts,result.stderr)
        print('M5-E1 UNSUPPORTED BUILD FLAGS REJECTED BEFORE ISO')
    print('M5-E1 ACTUAL NATIVE USER FAULT SURVIVAL ACCEPTANCE PASS')

if __name__=='__main__':main()
