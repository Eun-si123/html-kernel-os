#!/usr/bin/env python3
"""M5-E3-C: real Ring3 INT80 with poisoned saved user RSP or end RIP.

The CPU itself switches stacks via trusted TSS.RSP0; no malformed user
pointer may be dereferenced. On a recognized active task only that task ends.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from build_user_image import build as build_image
from test_boot import ROOT
from test_m5_interactive_run import APP_TRACE, BASE, HTML, build as build_legacy, exercise
from test_m5_user_fault_recovery import build as build_recover
from test_m5_user_timeout import build as build_timer, CPU, TIMER

# Five independent actual Ring3 programs with an invalid user saved stack
# or an INT80 exactly at the end of its validated executable image.
CASES={
    'null': 'movabsq $0,%rsp',
    'code': 'movabsq $0x0000400000000000,%rsp',
    'kernel': 'movabsq $0xffffffff80001000,%rsp',
    'above': 'movabsq $0x0000400000002010,%rsp',
    'end': None,
}

def make_app(work:Path,root:Path,name:str)->Path:
    asm=work/(name+'.S')
    stack_change=CASES[name]
    text='.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n'
    if stack_change:text+=f'  {stack_change}\n'
    text+='  movq $0x1234,%rdi\n  xorq %rax,%rax\n  int $0x80\n'
    if name!='end':text+='  ud2\n'
    text+='.section .note.GNU-stack,"",@progbits\n'
    asm.write_text(text)
    build_image(asm,root/f'bad-{name}.hke')
    return asm


def exercise_guest(work:Path,cache:Path,romfs:Path,*,timer:bool)->None:
    iso=work/('timer-invalid-frames.iso' if timer else 'no-timer-invalid-frames.iso')
    args=('--romfs-root',str(romfs),'--user-app-html',
          str(ROOT/'examples/user-programs/html-hello.html'))
    if timer:build_timer(ROOT/'examples/kernel.html',iso,work,cache,*args)
    else:build_recover(ROOT/'examples/kernel.html',iso,work,cache,*args)
    expected=APP_TRACE.replace(b'M5_C_USER_PAGES_READY\n',
                                b'M5_C_USER_PAGES_READY\n'+TIMER) if timer else APP_TRACE
    cmds=[(b'help\r',b'M5_HELP help ls cat /path run /path exit')]
    for case in CASES:
        cmds.extend(((f'run /bad-{case}.hke\r'.encode(),b'M5_ERR_USER_SYSCALL'),
                     (b'run /apps/hello.hke\r',expected)))
    cmds.append((b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML))
    for boot in range(2):
        trace,uart=exercise(iso,cmds,HTML,cpu=CPU if timer else None)
        assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
        # The dedicated EOF repair classifies last-byte INT80 separately
        # from a poisoned saved stack; BOTH retire the same verified app.
        assert trace.count(b'M5_E_USER_BAD_SYSCALL_FRAME\n')==4,(boot,trace)
        assert trace.count(b'M5_E_USER_EOF_SYSCALL_REJECTED\n')==1,(boot,trace)
        assert trace.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==5,(boot,trace)
        assert trace.count(b'M5_ERR_USER_SYSCALL\n')==5,(boot,trace)
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==5,(boot,trace)
        assert trace.count(b'M5_RUN_DONE\n')==5,(boot,trace)
        assert trace.count(expected)==5,(boot,trace)
        assert uart.count(b'M5_ERR_USER_SYSCALL')==5,(boot,uart)
        assert uart.count(b'M5_C_USER_VALUE=2026')==5,(boot,uart)
        assert b'M4_BAD_RING3_SYSCALL_FRAME' not in trace
        assert b'M5_C_INVALID_SYSCALL_ADDRESS_SPACE' not in trace
        if timer: assert trace.count(TIMER)==10,(boot,trace)
        print(f'M5-E3-C REAL QEMU {"x2APIC" if timer else "NO-TIMER"} BOOT {boot+1}/2: '
              '5 BAD USER FRAMES + 5 HTML USER RERUNS + CLEAN EXIT PASS',flush=True)


def prove_combined_text_and_bad_frame(work:Path,cache:Path,romfs:Path)->None:
    """Merged F2 code-page text pointer copyin survives E3-C task cleanup."""
    from test_m5_html_user_text import TRACE,TEXT
    from test_m5_user_timeout import SPIN_TRACE
    root=work/'text-romfs'
    # ROMFS is intentionally bounded to 16 files. Rebuild a *minimal*
    # fixture root rather than copying the five other failure probes;
    # loader automatically adds 10 built-in app/fault test images.
    shutil.copytree(ROOT/'examples/romfs',root)
    shutil.copy2(romfs/'bad-null.hke',root/'bad-null.hke')
    build_image(ROOT/'examples/user-programs/bad-text-pointer.S',
                root/'bad-text-pointer.hke')
    iso=work/'combined-text-user-frame.iso'
    build_timer(ROOT/'examples/kernel.html',iso,work,cache,
                '--romfs-root',str(root),'--user-app-html',
                str(ROOT/'examples/user-programs/html-message.html'))
    cmds=[
        (b'run /apps/hello.hke\r',TRACE),
        (b'run /bad-null.hke\r',b'M5_ERR_USER_SYSCALL'),
        (b'run /apps/hello.hke\r',TRACE),
        (b'run /bad-text-pointer.hke\r',b'M5_ERR_USER_SYSCALL'),
        (b'run /apps/hello.hke\r',TRACE),
        (b'run /apps/spin.hke\r',SPIN_TRACE),
        (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
    ]
    transcript,uart=exercise(iso,cmds,HTML,cpu=CPU)
    assert transcript.count(TRACE)==3,transcript
    assert transcript.count(TEXT)==3,transcript
    assert uart.count(TEXT)==3,uart
    assert transcript.count(b'M5_E_USER_BAD_SYSCALL_FRAME\n')==1,transcript
    assert transcript.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==2,transcript
    assert transcript.count(b'M5_ERR_USER_SYSCALL\n')==2,transcript
    assert transcript.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,transcript
    assert transcript.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==3,transcript
    assert b'M4_BAD_RING3_SYSCALL_FRAME' not in transcript
    assert b'\x1b[' not in uart
    print('M5-E3-C+F2 REAL QEMU: 3 HTML TEXT USERS + MALFORMED FRAME + BAD USER POINTER + x2APIC TIMEOUT PASS',flush=True)


def prove_original_fatal(work:Path,cache:Path,source:Path)->None:
    iso=work/'legacy-fatal.iso'
    build_legacy(ROOT/'examples/kernel.html',iso,work,cache,
                 ['--user-app-source',str(source)])
    with tempfile.TemporaryDirectory(prefix='htmlk-e3c-fatal-') as td:
        log=Path(td)/'debugcon.log'
        cmd=['qemu-system-x86_64','-M','q35','-m','256M',
             '-cdrom',str(iso),'-boot','d','-display','none',
             '-monitor','none','-net','none','-serial','stdio',
             '-debugcon','file:'+str(log),'-global','isa-debugcon.iobase=0xe9',
             '-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-no-reboot']
        guest=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        def current()->bytes:return log.read_bytes() if log.is_file() else b''
        try:
            start=time.monotonic()
            while BASE not in current():
                assert guest.poll() is None and time.monotonic()-start<17
                time.sleep(.019)
            for byte in b'run /apps/hello.hke\r':
                assert guest.stdin is not None
                guest.stdin.write(bytes((byte,)));guest.stdin.flush();time.sleep(.007)
            _,stderr=guest.communicate(timeout=12)
            trace=current()
            assert guest.returncode==53,(guest.returncode,trace,stderr)
            assert b'M4_BAD_RING3_SYSCALL_FRAME' in trace,trace
            assert b'M5_E_USER_BAD_SYSCALL_FRAME' not in trace,trace
            assert trace.count(b'M5_PROMPT> ')==1,trace
        finally:
            if guest.poll() is None:guest.kill();guest.communicate(timeout=4)
    print('M5-E3-C NO RECOVERY FLAG: LEGACY FATAL GUEST EXIT53 STILL ENFORCED',flush=True)


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3c-') as td:
        work=Path(td)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        romfs=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',romfs)
        sources={case:make_app(work,romfs,case) for case in CASES}
        exercise_guest(work,cache,romfs,timer=False)
        exercise_guest(work,cache,romfs,timer=True)
        prove_combined_text_and_bad_frame(work,cache,romfs)
        prove_original_fatal(work,cache,sources['null'])
    print('M5-E3-C NATIVE CPU MALFORMED CPL3 INT80 FRAME RECOVERY + LEGACY FAIL-STOP PASS')

if __name__=='__main__':main()
