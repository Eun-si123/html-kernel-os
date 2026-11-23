#!/usr/bin/env python3
"""True x86-64 CPL3 #DB/#BP trap (not a fault) with poisoned saved user RSP."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile

from build_user_image import build as build_image
from test_boot import ROOT, boot
from test_m5_interactive_run import exercise,HTML
from test_m5_user_timeout import build as build_timer,CPU,SPIN_TRACE
from test_m5_user_fault_recovery import build as build_no_timer
from test_m5_user_loader import make_iso as make_legacy
from test_m5_user_bad_ud_stack import BAD_USER_STACKS

FAULT=b'M5_ERR_USER_FAULT\n'
RECLAIM=b'M5_E_FAULT_FRAMES_RECLAIMED\n'
GOOD=b'M5_C_USER_FRAMES_RECLAIMED\n'
PROGRAM=ROOT/'examples/user-programs/html-message.html'
CASE_LIST=(('db-null','null','f1',1),
           ('bp-code','code','cc',3),
           ('db-kernel','kernel','f1',1),
           ('bp-above','above','cc',3))

def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3i-true-trap-') as td:
        work=Path(td)
        cache=Path(os.getenv('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        romfs=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',romfs)
        files={}
        for case,stack,opcode,vector in CASE_LIST:
            asm=work/(case+'.S')
            asm.write_text('.section .text\n.global htmlk_user_program_start\n'
                           'htmlk_user_program_start:\n'
                           f' {BAD_USER_STACKS[stack]}\n'
                           f' .byte 0x{opcode}\n'
                           '.section .note.GNU-stack,"",@progbits\n')
            build_image(asm,romfs/(case+'.hke'))
            files[case]=asm
        # INT $3 is two-byte trap; its saved RIP points one-past-end.
        asm=work/'bp-int-end.S'
        asm.write_text('.section .text\n.global htmlk_user_program_start\n'
                       'htmlk_user_program_start:\n'
                       ' xorq %rsp,%rsp\n int $3\n'
                       '.section .note.GNU-stack,"",@progbits\n')
        build_image(asm,romfs/'bp-int-end.hke')
        # With M5-E2 timer: 2 base ROMFS + 9 generated apps + 5 cases =16.
        no_timer=work/'no-timer.iso'
        build_no_timer(ROOT/'examples/kernel.html',no_timer,work,cache,
                       '--romfs-root',str(romfs),'--user-app-html',str(PROGRAM))
        commands=[
            (b'run /db-null.hke\r',FAULT),
            (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n'),
            (b'run /bp-code.hke\r',FAULT),
            (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n'),
            (b'run /bp-int-end.hke\r',FAULT),
            (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n'),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)]
        serial,uart=exercise(no_timer,commands,HTML)
        assert serial.count(b'M5_E3_USER_DB_BAD_RSP_RETIRED\n')==1
        assert serial.count(b'M5_E3_USER_BP_BAD_RSP_RETIRED\n')==2
        assert serial.count(RECLAIM)==serial.count(GOOD)==3
        assert b'M5_E2_X2APIC_TIMER_READY' not in serial
        print('M5-E3-I E1 no-timer actual CPU #DB/#BP/INT3, code-end RIP, 3 HTML reruns PASS',flush=True)

        iso=work/'timer.iso'
        build_timer(ROOT/'examples/kernel.html',iso,work,cache,
                    '--romfs-root',str(romfs),'--user-app-html',str(PROGRAM))
        operations=[(b'help\r',b'M5_HELP help ls cat /path run /path exit')]
        for case,*_ in CASE_LIST:
            operations.extend(((f'run /{case}.hke\r'.encode(),FAULT),
                               (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n')))
        operations.extend(((b'run /bp-int-end.hke\r',FAULT),
                           (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n'),
                           (b'run /apps/spin.hke\r',SPIN_TRACE),
                           (b'run /apps/hello.hke\r',b'M5_RUN_DONE\n'),
                           (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)))
        for iteration in range(3):
            serial,uart=exercise(iso,operations,HTML,cpu=CPU)
            assert serial.count(b'M5_E3_USER_DB_BAD_RSP_RETIRED\n')==2,serial
            assert serial.count(b'M5_E3_USER_BP_BAD_RSP_RETIRED\n')==3,serial
            assert serial.count(FAULT)==5 and serial.count(RECLAIM)==5,serial
            assert serial.count(GOOD)==6 and serial.count(b'M5_RUN_DONE\n')==6,serial
            assert serial.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,serial
            assert serial.count(b'M5_E2_REAL_USER_IRQ_LIMIT\n')==1,serial
            assert serial.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            print(f'M5-E3-I QEMU {iteration+1}/3: 5 genuine CPL3 DB/BP traps, '
                  '6 healthy HTML reruns, real x2APIC timeout, safe recovery PASS',flush=True)

        # Preserve preexisting M5-C1 policy: no guarded user recovery.
        for case,expected in (('db-null','01'),('bp-code','0D')):
            legacy=work/('legacy-'+case+'.iso')
            make_legacy(ROOT/'examples/kernel.html',legacy,work,cache,
                        '--user-app-source',str(files[case]))
            code,trace=boot(legacy,timeout=20)
            # Legacy INT3 uses a non-user-callable DPL0 gate, therefore
            # CPU rejects the software interrupt with #GP vector 13.
            assert code==45 and 'M3_EXCEPTION V='+expected in trace,(case,code,trace)
        print('M5-E3-I real legacy #DB and #BP->#GP fatal exit45 controls PASS',flush=True)

if __name__=='__main__':
    main()
