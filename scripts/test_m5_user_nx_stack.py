"""M5-E3-N: actual CPU execute denial on the private writable stack."""
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
FAULT=b"M5_ERR_USER_FAULT\n"
NX=b"M5_E3_USER_NX_STACK_RETIRED\n"
HEADER=".section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n"
# A one-byte RET routine on our own stack; on the baseline it executes
# successfully. On the NX build the actual instruction fetch must fault.
BODY=""" movb $0xc3,-16(%rsp)
 leaq -16(%rsp),%rax
 call *%rax
 movq $0,%rax
 movq $0x1234,%rdi
 int $0x80
 movq $2,%rax
 movq $2026,%rdi
 int $0x80
 movq $1,%rax
 xorq %rdi,%rdi
 int $0x80
 ud2
.section .note.GNU-stack,"",@progbits
"""

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-nx-stack-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        root=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",root)
        asm=work/"stack.S"
        asm.write_text(HEADER+BODY)
        build_image(asm,root/"stack.hke")
        for timed in (False,True):
            iso=work/("timed.iso" if timed else "plain.iso")
            (timed_build if timed else plain)(ROOT/"examples/kernel.html",iso,work,cache,"--romfs-root",str(root))
            if not timed:
                # Same binary, actual CPU advertises no NX capability.
                log,uart=exercise(iso,[(b"run /stack.hke\r",GOOD),
                    (b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)],HTML,cpu="qemu64,-nx")
                for data in (log,uart):
                    assert data.count(b"M5_C_USER_VALUE=2026\n")==1 and NX not in data,data
                print("M5-E3-N CPU without NX retains legacy execution (not protected)",flush=True)
            cmds=[(b"run /stack.hke\r",FAULT),(b"run /apps/hello.hke\r",GOOD),
                  (b"run /stack.hke\r",FAULT),(b"run /apps/hello.hke\r",GOOD)]
            if timed:
                cmds += [(b"run /apps/spin.hke\r",SPIN_TRACE),(b"run /apps/hello.hke\r",GOOD)]
            cmds += [(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)]
            for attempt in range(3 if timed else 1):
                log,uart=exercise(iso,cmds,HTML,cpu=CPU if timed else None)
                for data in (log,uart):
                    assert data.count(NX)==2 and data.count(FAULT)==2,data
                    assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==2,data
                    assert data.count(b"M5_C_USER_VALUE=2026\n")==2+int(timed),data
                    assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==2+int(timed),data
                    assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data
                print(f"M5-E3-N actual NX stack fetch denied, shell survives timed={timed} run={attempt+1} PASS",flush=True)
if __name__=="__main__":main()
