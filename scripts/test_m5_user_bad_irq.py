#!/usr/bin/env python3
"""M5-E3-D: actual CPU x2APIC aborts owned CPL3 spin with poisoned RSP."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile

from build_user_image import build as build_image
from test_boot import ROOT
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import build, CPU, SPIN_TRACE
from test_m5_html_user_text import TRACE, TEXT

# Ordinary user registers only; no syscall, yield or memory dereference.
# A bad user stack register is enough to defeat the old timer frame guard.
BAD_STACKS={
    'null': 'xorq %rsp,%rsp',
    'code': 'movabsq $0x0000400000000000,%rsp',
    'kernel': 'movabsq $0xffffffff80001000,%rsp',
    'above': 'movabsq $0x0000400000002010,%rsp',
}
MARKER=b'M5_E3_USER_IRQ_FRAME_INVALID\n'
TIMEOUT=b'M5_E2_CPL3_TIMEOUT\n'
RECLAIM=b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n'

def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3d-irq-') as folder:
        work=Path(folder)
        root=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',root)
        for name,stack in BAD_STACKS.items():
            asm=work/(name+'.S')
            asm.write_text(''.join((
                '.section .text\n.global htmlk_user_program_start\n',
                'htmlk_user_program_start:\n',
                f'  {stack}\n',
                '.Lforever:\n  incq %rax\n  jmp .Lforever\n',
                '.section .note.GNU-stack,"",@progbits\n')))
            build_image(asm,root/(f'bad-{name}.hke'))
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        iso=work/'bad-user-rsp-timer.iso'
        build(ROOT/'examples/kernel.html',iso,work,cache,
              '--romfs-root',str(root),
              '--user-app-html',str(ROOT/'examples/user-programs/html-message.html'))
        commands=[(b'help\r',b'M5_HELP help ls cat /path run /path exit')]
        for name in BAD_STACKS:
            commands.extend(((f'run /bad-{name}.hke\r'.encode(),b'M5_ERR_USER_TIMEOUT'),
                             (b'run /apps/hello.hke\r',TRACE)))
        commands.extend(((b'run /apps/spin.hke\r',SPIN_TRACE),
                         (b'run /apps/hello.hke\r',TRACE),
                         (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)))
        for boot in range(3):
            trace,uart=exercise(iso,commands,HTML,cpu=CPU)
            assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert trace.count(MARKER)==4,(boot,trace)
            assert trace.count(TIMEOUT)==5,(boot,trace)
            assert trace.count(RECLAIM)==5,(boot,trace)
            assert trace.count(b'M5_ERR_USER_TIMEOUT\n')==5,(boot,trace)
            assert trace.count(TRACE)==5,(boot,trace)
            assert trace.count(TEXT)==5,(boot,trace)
            assert uart.count(TEXT)==5,(boot,uart)
            assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==5,(boot,trace)
            assert trace.count(b'M5_E2_REAL_USER_IRQ_LIMIT\n')==1,(boot,trace)
            assert b'M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT' not in trace
            assert b'M4_USER_FRAME_LEAK' not in trace
            print(f'M5-E3-D BOOT {boot+1}/3: 4 INVALID CPL3 RSP SPINS -> REAL IRQ ABORT + '
                  '5 SUCCESSFUL HTML TEXT RERUNS + CLEAN EXIT PASS',flush=True)
    print('M5-E3-D GENUINE x2APIC MALFORMED USER IRQ FRAME CONTAINMENT PASS',flush=True)

if __name__=='__main__':main()
