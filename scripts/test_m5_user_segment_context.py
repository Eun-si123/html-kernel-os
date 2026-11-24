"""M5-E3-M: actual FS/GS selector and zero-base checks across app runs."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML
from test_m5_user_fault_recovery import build as plain
from test_m5_user_timeout import build as timed_build, CPU, SPIN_TRACE
from build_user_image import build as build_image

GOOD=b"M5_RUN_DONE\n"
HEADER=".section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n"
DIRTY=""" movw $0x33,%ax
 movw %ax,%fs
 movw %ax,%gs
 movq $2026,%r12
"""
CHECK=""" xorq %r12,%r12
 movw %fs,%ax
 testw %ax,%ax
 jnz report
 movw %gs,%ax
 testw %ax,%ax
 jnz report
 movq $2026,-8(%rsp)
 movq %fs:-8(%rsp),%rax
 cmpq $2026,%rax
 jne report
 movq %gs:-8(%rsp),%rax
 cmpq $2026,%rax
 jne report
 movq $2026,%r12
"""
REPORT="""report:
 movq $0,%rax
 movq $0x1234,%rdi
 int $0x80
 movq $2,%rax
 movq %r12,%rdi
 int $0x80
 movq $1,%rax
 xorq %rdi,%rdi
 int $0x80
 ud2
.section .note.GNU-stack,"",@progbits
"""

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-segment-context-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        root=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",root)
        # The first nonterminal syscall must not clear the running task's
        # selected segment registers. Test this on the same dirty app.
        dirty_report=REPORT.replace(" movq $2,%rax", """ movw %fs,%ax
 cmpw $0x33,%ax
 jne lost
 movw %gs,%ax
 cmpw $0x33,%ax
 je still_live
lost:
 xorq %r12,%r12
still_live:
 movq $2,%rax""",1)
        for name,body in [("dirtyseg",DIRTY+dirty_report),("checkseg",CHECK+REPORT),("segfault",DIRTY+" ud2\n")]:
            asm=work/(name+".S")
            asm.write_text(HEADER+body)
            build_image(asm,root/(name+".hke"))
        for timed in (False,True):
            if timed:
                asm=work/"segspin.S"
                asm.write_text(HEADER+DIRTY+"1: jmp 1b\n")
                build_image(asm,root/"segspin.hke")
            iso=work/("timed.iso" if timed else "plain.iso")
            (timed_build if timed else plain)(ROOT/"examples/kernel.html",iso,work,cache,"--romfs-root",str(root))
            cmds=[(b"run /checkseg.hke\r",GOOD),(b"run /dirtyseg.hke\r",GOOD),
                  (b"run /checkseg.hke\r",GOOD),(b"run /segfault.hke\r",b"M5_ERR_USER_FAULT\n"),
                  (b"run /checkseg.hke\r",GOOD)]
            if timed:
                cmds += [(b"run /segspin.hke\r",SPIN_TRACE.replace(b"/apps/spin.hke",b"/segspin.hke")),
                         (b"run /checkseg.hke\r",GOOD)]
            cmds += [(b"run /apps/hello.hke\r",GOOD),(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)]
            for attempt in range(3 if timed else 1):
                log,uart=exercise(iso,cmds,HTML,cpu=CPU if timed else None)
                for data in (log,uart):
                    assert data.count(b"M5_C_USER_VALUE=2026\n")==5+int(timed) and b"M5_C_USER_VALUE=0\n" not in data,data
                    assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==5+int(timed),data
                    assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==1,data
                    assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data
                print(f"M5-E3-M fresh FS/GS selector and zero-base access timed={timed} run={attempt+1} PASS",flush=True)
if __name__=="__main__":main()
