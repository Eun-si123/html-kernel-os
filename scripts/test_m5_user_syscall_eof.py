#!/usr/bin/env python3
"""M5-E3: genuine Ring3 INT 0x80 at HKEX EOF must not kill live shell.

A terminating syscall may be at the final instruction; a non-exit syscall
at EOF must retire only its process, not return with invalid user RIP.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from build_user_image import build as build_user
from test_boot import ROOT
from test_m5_interactive_run import APP_TRACE,BASE,HTML,exercise
from test_m5_user_fault_recovery import build as build_e1
from test_m5_user_timeout import build as build_e2,CPU,TIMER,SPIN_TRACE
from test_m5_user_loader import make_iso,PREFIX

PROGRAMS={
 'unknown-eof': '''.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n    movq $99,%rax\n    int $0x80\n.section .note.GNU-stack,"",@progbits\n''',
 'report-eof': '''.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n    movq $0x1234,%rdi\n    xorq %rax,%rax\n    int $0x80\n    movl $2026,%edi\n    movl $2,%eax\n    int $0x80\n.section .note.GNU-stack,"",@progbits\n''',
 'exit-eof': '''.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n    movq $0x1234,%rdi\n    xorq %rax,%rax\n    int $0x80\n    movl $2026,%edi\n    movl $2,%eax\n    int $0x80\n    xorl %edi,%edi\n    movl $1,%eax\n    int $0x80\n.section .note.GNU-stack,"",@progbits\n''',
}

def write_programs(work:Path,romfs:Path)->dict[str,Path]:
    sources={}
    for name,assembly in PROGRAMS.items():
        source=work/(name+'.S')
        source.write_text(assembly)
        build_user(source,romfs/(name+'.hke'))
        sources[name]=source
    build_user(ROOT/'examples/user-programs/hello.S',romfs/'good.hke')
    return sources


def verify_real_guest(work:Path,romfs:Path,cache:Path,*,timer:bool,
                      text_app:bool)->None:
    label=('timer' if timer else 'no-timer')+('-html-text' if text_app else '')
    iso=work/(label+'.iso')
    args=['--romfs-root',str(romfs)]
    if text_app:
        args += ['--user-app-html',str(ROOT/'examples/user-programs/html-message.html')]
    (build_e2 if timer else build_e1)(ROOT/'examples/kernel.html',iso,work,cache,*args)
    prefix=b'M5_C_ROMFS_PROGRAM_LOADED\nM5_C_USER_PAGES_READY\n'+(TIMER if timer else b'')
    good=APP_TRACE.replace(b'/apps/hello.hke',b'/good.hke')
    if timer:
        good=good.replace(b'M5_C_USER_PAGES_READY\n',
                          b'M5_C_USER_PAGES_READY\n'+TIMER)
    exit_trace=(b'M5_RUN_START /exit-eof.hke\n'+prefix+
                b'M5_C_RING3_STACK_OK\nM5_C_USER_VALUE=2026\n'
                b'M5_C_RING3_EXIT_OK\nM5_C_USER_FRAMES_RECLAIMED\n'
                b'M5_RUN_DONE\nM5_PROMPT> ')
    actions=[(b'run /good.hke\r',good)]
    for name in ('unknown-eof','report-eof'):
        actions.append((f'run /{name}.hke\r'.encode(),b'M5_ERR_USER_SYSCALL\n'))
        actions.append((b'help\r',b'M5_HELP help ls cat /path run /path exit'))
        actions.append((b'run /good.hke\r',good))
    actions.extend(((b'run /exit-eof.hke\r',exit_trace),
                    (b'run /good.hke\r',good)))
    if text_app:
        from test_m5_html_user_text import TRACE,TEXT
        # This independently compiled HTML user string must remain intact.
        actions.append((b'run /apps/hello.hke\r',TRACE))
    if timer:
        actions.append((b'run /apps/spin.hke\r',SPIN_TRACE))
        actions.append((b'run /good.hke\r',good))
    actions.append((b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML))
    expected_normal=5+(1 if timer else 0)+(1 if text_app else 0)
    for repetition in range(2):
        trace,uart=exercise(iso,actions,HTML,**({'cpu':CPU} if timer else {}))
        assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML),trace
        assert trace.count(b'M5_E_USER_EOF_SYSCALL_REJECTED\n')==2,trace
        assert trace.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==2,trace
        assert trace.count(b'M5_ERR_USER_SYSCALL\n')==2,trace
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==expected_normal,trace
        assert trace.count(b'M5_RUN_DONE\n')==expected_normal,trace
        assert trace.count(exit_trace)==1,trace
        assert uart.count(b'M5_ERR_USER_SYSCALL\n')==2,uart
        assert uart.count(b'M5_C_USER_VALUE=2026')==expected_normal-(1 if text_app else 0),uart
        assert b'M4_BAD_RING3_SYSCALL_FRAME' not in trace,trace
        if timer:
            assert trace.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,trace
            assert trace.count(TIMER)==expected_normal+2+1,trace
        if text_app:
            assert trace.count(TEXT)==1 and uart.count(TEXT)==1,(trace,uart)
        print(f'M5-E3 REAL QEMU {label} {repetition+1}/2: EOF INVALID/REPORT ABORT, VALID EOF EXIT, RE-RUN AND CLEAN UART PASS',flush=True)


def verify_legacy(work:Path,cache:Path,sources:dict[str,Path])->None:
    from test_boot import boot
    for name in ('unknown-eof','report-eof','exit-eof'):
        iso=work/('legacy-'+name+'.iso')
        make_iso(ROOT/'examples/kernel.html',iso,work,cache,
                 '--user-app-source',str(sources[name]))
        code,trace=boot(iso,timeout=18)
        assert code==53,(name,code,trace)
        assert trace.startswith(PREFIX),(name,trace)
        assert trace.endswith('M4_BAD_RING3_SYSCALL_FRAME\n'),(name,trace)
        assert b'M5_E_USER_EOF_SYSCALL_REJECTED' not in trace.encode(),trace
    print('M5-E3 LEGACY LOADER: EOF INT80 CONTINUES FAIL-STOP (QEMU EXIT 53) PASS',flush=True)


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3-syscall-eof-') as directory:
        work=Path(directory)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        romfs=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',romfs)
        sources=write_programs(work,romfs)
        verify_real_guest(work,romfs,cache,timer=False,text_app=False)
        verify_real_guest(work,romfs,cache,timer=True,text_app=False)
        verify_real_guest(work,romfs,cache,timer=True,text_app=True)
        verify_legacy(work,cache,sources)
    print('M5-E3 POSTINSTRUCTION SYSCALL EOF / CLEAN SHELL REAL CPU ACCEPTANCE PASS')

if __name__=='__main__':main()
