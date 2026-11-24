"""M5-E3-L: real x87 state isolation for the existing one-app loader."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML
from test_m5_user_fault_recovery import build as build_plain
from test_m5_user_timeout import build as build_timed, CPU, SPIN_TRACE
from build_user_image import build as build_image

GOOD=b"M5_RUN_DONE\n"
VALUE=b"M5_C_USER_VALUE=2026\n"
BAD=b"M5_C_USER_VALUE=0\n"
HEADER=".section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n"
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
# Change control word and all eight physical registers. Leave seven full.
DIRTY=""" movq $2026,%r12
 pushq $0x077f
 fldcw (%rsp)
 addq $8,%rsp
 fld1; fldpi; fld1; fldpi; fld1; fldpi; fld1; fldpi
 fstp %st(0)
"""
# Read a 108-byte FNSAVE image, not any kernel or other task address.
# Check architectural defaults and the physical register payload bytes.
CHECK=""" subq $128,%rsp
 fnsave (%rsp)
 movq $2026,%r12
 cmpw $0x037f,0(%rsp)
 jne bad
 cmpw $0,4(%rsp)
 jne bad
 cmpw $0xffff,8(%rsp)
 jne bad
 leaq 28(%rsp),%rsi
 movq $80,%rcx
check_byte:
 cmpb $0,(%rsi)
 jne bad
 incq %rsi
 decq %rcx
 jnz check_byte
 jmp done
bad:
 xorq %r12,%r12
done:
 addq $128,%rsp
"""
# Produce a pending unmasked invalid-operation exception without a
# subsequent waiting x87 instruction; integer syscalls may still exit.
PENDING=""" movq $2026,%r12
 pushq $0x037e
 fldcw (%rsp)
 addq $8,%rsp
 fldz
 fldz
 fdivp %st,%st(1)
"""

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-x87-context-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        root=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",root)
        for name,body in [
            ("dirty",DIRTY+REPORT), ("check",CHECK+REPORT),
            ("pending",PENDING+REPORT),
            ("fxfault",DIRTY+" ud2\n"),
        ]:
            asm=work/(name+".S")
            asm.write_text(HEADER+body)
            build_image(asm,root/(name+".hke"))
        # Keep reserved builder apps/ untouched; add a separate dirty spin.
        for timed in (False,True):
            if timed:
                asm=work/"fxspin.S"
                asm.write_text(HEADER+DIRTY+"1: jmp 1b\n")
                build_image(asm,root/"fxspin.hke")
            iso=work/("timed.iso" if timed else "plain.iso")
            (build_timed if timed else build_plain)(ROOT/"examples/kernel.html",iso,work,cache,"--romfs-root",str(root))
            cmds=[(b"run /check.hke\r",GOOD),(b"run /dirty.hke\r",GOOD),
                  (b"run /check.hke\r",GOOD),(b"run /pending.hke\r",GOOD),
                  (b"run /check.hke\r",GOOD),(b"run /fxfault.hke\r",b"M5_ERR_USER_FAULT\n"),
                  (b"run /check.hke\r",GOOD)]
            if timed:
                cmds += [(b"run /fxspin.hke\r",SPIN_TRACE.replace(b"/apps/spin.hke",b"/fxspin.hke")),(b"run /check.hke\r",GOOD)]
            cmds += [(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)]
            for attempt in range(3 if timed else 1):
                log,uart=exercise(iso,cmds,HTML,cpu=CPU if timed else None)
                for data in (log,uart):
                    assert data.count(VALUE)==6+int(timed) and BAD not in data,data
                    assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==6+int(timed),data
                    assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==1,data
                    assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data
                print(f"M5-E3-L fresh x87 control/status/tags/80-byte data after exit/fault/timeout timed={timed} run={attempt+1} PASS",flush=True)

if __name__=="__main__":main()
