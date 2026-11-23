#!/usr/bin/env python3
"""M5-E3-F genuine CPL3 #DE with poisoned user RSP -> process-only abort.

Regression: a real DIV0 with RSP=0 previously killed the whole kernel
(QEMU exit 45). Tests the exact 5-word CPU exception frame, not software
simulated messages or the 160-byte timer/syscall IRQ frame.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile
from build_user_image import build as build_image
from test_boot import ROOT,boot
from test_m5_html_user_text import TRACE, TEXT
from test_m5_interactive_run import exercise,BASE,HTML
from test_m5_user_timeout import build,CPU,SPIN_TRACE,TIMER
from test_m5_user_fault_recovery import build as build_no_timer
from test_m5_user_loader import make_iso as make_legacy

# Reuse the exact independent bad-user-RSP fixtures from the #UD suite.
from test_m5_user_bad_ud_stack import BAD_USER_STACKS
MARKER=b'M5_E3_USER_DE_BAD_RSP_RETIRED\n'
FAULT=b'M5_ERR_USER_FAULT\n'
RECLAIM=b'M5_E_FAULT_FRAMES_RECLAIMED\n'
GOOD=b'M5_C_USER_FRAMES_RECLAIMED\n'


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-bad-user-de-') as td:
        work=Path(td)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        root=work/'romfs';shutil.copytree(ROOT/'examples/romfs',root)
        for name,stack in BAD_USER_STACKS.items():
            asm=work/(name+'.S')
            asm.write_text('.section .text\n.global htmlk_user_program_start\n'
                           'htmlk_user_program_start:\n'
                           f' {stack}\n xorq %rdx,%rdx\n movq $19,%rax\n xorq %rcx,%rcx\n divq %rcx\n ud2\n'
                           '.section .note.GNU-stack,"",@progbits\n')
            build_image(asm,root/(f'bad-de-{name}.hke'))
        # No timer: #DE recovery must work from the real CPU privilege
        # transition even if the user RSP has been corrupted.
        no_timer=work/'no-timer.iso'
        build_no_timer(ROOT/'examples/kernel.html',no_timer,work,cache,
                       '--romfs-root',str(root),
                       '--user-app-html',str(ROOT/'examples/user-programs/html-message.html'))
        expected_good=TRACE.replace(TIMER,b'')
        e1_actions=[
           (b'run /bad-de-null.hke\r',FAULT),
           (b'run /apps/hello.hke\r',expected_good),
           (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
        ]
        trace,uart=exercise(no_timer,e1_actions,HTML)
        assert MARKER in trace and trace.count(RECLAIM)==1,trace
        assert trace.count(GOOD)==1 and uart.count(TEXT)==1,(trace,uart)
        assert b'M5_E2_X2APIC_TIMER_READY' not in trace
        print('M5-E3-F E1 NO-TIMER: ACTUAL DIV0 BAD RSP TASK ABORT, PRIVATE FRAME RECLAIM, UART RERUN PASS',flush=True)
        iso=work/'timer.iso'
        build(ROOT/'examples/kernel.html',iso,work,cache,
              '--romfs-root',str(root),
              '--user-app-html',str(ROOT/'examples/user-programs/html-message.html'))
        operations=[(b'help\r',b'M5_HELP help ls cat /path run /path exit')]
        for name in BAD_USER_STACKS:
            operations.extend(((f'run /bad-de-{name}.hke\r'.encode(),FAULT),
                               (b'run /apps/hello.hke\r',TRACE)))
        operations.extend(((b'run /apps/spin.hke\r',SPIN_TRACE),
                           (b'run /apps/hello.hke\r',TRACE),
                           (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)))
        for attempt in range(3):
            trace,uart=exercise(iso,operations,HTML,cpu=CPU)
            assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert trace.count(MARKER)==4,(attempt,trace)
            assert trace.count(RECLAIM)==4,(attempt,trace)
            assert trace.count(FAULT)==4,(attempt,trace)
            assert trace.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,(attempt,trace)
            assert trace.count(GOOD)==5,(attempt,trace)
            assert trace.count(TRACE)==5,(attempt,trace)
            assert uart.count(TEXT)==5,(attempt,uart)
            assert uart.count(FAULT)==4,(attempt,uart)
            assert b'M3_EXCEPTION V=00' not in trace
            assert b'M4_USER_FRAME_LEAK' not in trace
            assert b'M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT' not in trace
            print(f'M5-E3-F QEMU {attempt+1}/3: 4 DIFFERENT INVALID RSP DIV0, 5 HTML RERUNS, TRUE x2APIC, NO FATAL PASS',flush=True)
        legacy=work/'legacy.iso'
        make_legacy(ROOT/'examples/kernel.html',legacy,work,cache,
                    '--user-app-source',str(work/'null.S'))
        code,log=boot(legacy,timeout=18)
        assert code==45 and 'M3_EXCEPTION V=00' in log,(code,log)
        assert 'M5_E3_USER_DE_BAD_RSP_RETIRED' not in log and 'M5_RUN_DONE' not in log
        print('M5-E3-F LEGACY M5-C1 #DE WITH BAD RSP REMAINS FAIL-STOP EXIT45',flush=True)
    print('M5-E3-F FULL ACTUAL CPU TRUSTED #DE FRAME/OWNER RECOVERY ACCEPTANCE PASS')

if __name__=='__main__':main()
