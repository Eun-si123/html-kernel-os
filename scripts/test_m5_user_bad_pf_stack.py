#!/usr/bin/env python3
"""M5-E3-H actual CPL3 #PF IST2 with poisoned user RSP and owned recovery.

Real QEMU positive/negative oracles, not a synthetic CPU-frame mock.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile

from build_user_image import build as build_image
from test_boot import ROOT, boot
from test_m5_interactive_run import exercise, HTML
from test_m5_user_timeout import build as build_timer, CPU, SPIN_TRACE
from test_m5_user_fault_recovery import build as build_no_timer
from test_m5_user_loader import make_iso as make_legacy
from test_m5_user_bad_ud_stack import BAD_USER_STACKS

PF5 = b'M5_E3_USER_PF5_BAD_RSP_RETIRED\n'
PF7 = b'M5_E3_USER_PF7_BAD_RSP_RETIRED\n'
RECLAIM = b'M5_E_FAULT_FRAMES_RECLAIMED\n'
FAULT = b'M5_ERR_USER_FAULT\n'
GOOD = b'M5_C_USER_FRAMES_RECLAIMED\n'
HTML_USER = ROOT / 'examples/user-programs/html-message.html'
ASM_HEADER = '.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n'
ASM_END = ' ud2\n.section .note.GNU-stack,"",@progbits\n'

def make_bad(root: Path, work: Path) -> Path:
    first = None
    for name, stack in BAD_USER_STACKS.items():
        src = work / f'bad-pf5-{name}.S'
        src.write_text(ASM_HEADER + f' {stack}\n'
                       ' movabsq $0xffffffff80001000,%rax\n'
                       ' movq (%rax),%rax\n' + ASM_END)
        build_image(src, root / f'bad-pf5-{name}.hke')
        if first is None: first = src
    src = work / 'bad-pf7-null.S'
    src.write_text(ASM_HEADER + ' xorq %rsp,%rsp\n'
                   ' movabsq $0x0000400000000000,%rax\n'
                   ' movq $0x12,(%rax)\n' + ASM_END)
    build_image(src, root / 'bad-pf7-null.hke')
    # Error-code negative: non-present user-space read, U/S=1 but error=4,
    # deliberately NOT admitted by PF5/PF7 narrow proven owner fallback.
    src = work / 'bad-pf4-null.S'
    src.write_text(ASM_HEADER + ' xorq %rsp,%rsp\n'
                   ' movabsq $0x0000400000005000,%rax\n'
                   ' movq (%rax),%rax\n' + ASM_END)
    build_image(src, root / 'bad-pf4-null.hke')
    assert first is not None
    return first

def main() -> None:
    with tempfile.TemporaryDirectory(prefix='htmlk-bad-user-pf-ist2-') as td:
        work = Path(td)
        cache = Path(os.environ.get('HTMLK_CACHE_DIR', str(ROOT/'build/.cache')))
        romfs = work / 'romfs'
        shutil.copytree(ROOT/'examples/romfs', romfs)
        first = make_bad(romfs, work)
        # Before attempting the x2APIC IRQ path, prove the same CPU IST2
        # user-PF recovery also works with user IF=0 / no timer.
        no_timer = work / 'no-timer.iso'
        build_no_timer(ROOT/'examples/kernel.html', no_timer, work, cache,
                       '--romfs-root', str(romfs),
                       '--user-app-html', str(HTML_USER))
        commands = [
            (b'run /bad-pf5-null.hke\r', FAULT),
            (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n'),
            (b'run /bad-pf7-null.hke\r', FAULT),
            (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n'),
            (b'exit\r', b'M5_CONSOLE_EXIT\n'+HTML),
        ]
        out, uart = exercise(no_timer, commands, HTML)
        assert out.count(PF5) == out.count(PF7) == 1, out
        assert out.count(RECLAIM) == 2 and out.count(GOOD) == 2, out
        assert out.count(b'M3_IST_PF_STACK_OK\n') == 2, out
        assert b'M5_E2_X2APIC_TIMER_READY' not in out
        print('M5-E3-H E1 NO TIMER: actual poisoned-RSP #PF5/#PF7 owned IST2 recovery PASS')

        # Non-present error4 is deliberately unhandled. Test it in the no-
        # timer ISO while the file fits, then remove it before the x2APIC
        # build (the ROMFS cap of 16 files is a safety contract).
        try:
            exercise(no_timer, [(b'run /bad-pf4-null.hke\r', FAULT)], HTML)
            raise AssertionError('unexpected bad RSP error4 recovery')
        except AssertionError as error:
            result = str(error)
            assert "'early exit', 45" in result and 'V=0E' in result, result
        print('M5-E3-H invalid #PF error4 bad RSP remains fatal QEMU exit45 PASS')
        (romfs / 'bad-pf4-null.hke').unlink()

        timed = work / 'timer.iso'
        build_timer(ROOT/'examples/kernel.html', timed, work, cache,
                    '--romfs-root', str(romfs),
                    '--user-app-html', str(HTML_USER))
        operations = [(b'help\r', b'M5_HELP help ls cat /path run /path exit')]
        for name in BAD_USER_STACKS:
            operations.extend(((f'run /bad-pf5-{name}.hke\r'.encode(), FAULT),
                               (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n')))
        operations.extend(((b'run /bad-pf7-null.hke\r', FAULT),
                           (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n'),
                           (b'run /apps/spin.hke\r', SPIN_TRACE),
                           (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n'),
                           (b'exit\r', b'M5_CONSOLE_EXIT\n'+HTML)))
        for attempt in range(3):
            out, uart = exercise(timed, operations, HTML, cpu=CPU)
            assert out.count(PF5) == 4 and out.count(PF7) == 1, (attempt,out)
            assert out.count(FAULT) == out.count(RECLAIM) == 5, (attempt,out)
            assert out.count(GOOD) == 6, (attempt,out)
            assert out.count(b'M3_IST_PF_STACK_OK\n') == 5, (attempt,out)
            assert out.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n') == 1, (attempt,out)
            assert out.endswith(b'M5_CONSOLE_EXIT\n'+HTML), (attempt,out)
            print(f'M5-E3-H genuine IST2 #PF5×4/#PF7×1, '
                  f'HTML reruns×6, x2APIC timeout QEMU {attempt+1}/3 PASS')

        # Older standalone M5-C1 must still fatal-trap a genuinely corrupt
        # user RSP. This preserves the opt-in fault-recovery boundary.
        legacy = work / 'legacy.iso'
        make_legacy(ROOT/'examples/kernel.html', legacy, work, cache,
                    '--user-app-source', str(first))
        code, output = boot(legacy, timeout=20)
        assert code == 45 and 'M3_EXCEPTION V=0E' in output, (code,output)
        print('M5-E3-H LEGACY M5-C1 REAL #PF V=0E fail-stop exit45 PASS')


if __name__ == '__main__':
    main()
