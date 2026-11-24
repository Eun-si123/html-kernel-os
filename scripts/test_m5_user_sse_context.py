"""M5-E3-O: real single-app x87/MMX/XMM/MXCSR context lifecycle."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML
from test_m5_user_fault_recovery import build as plain
from test_m5_user_timeout import build as timed_build, CPU, SPIN_TRACE
from build_user_image import build as build_image

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
GOOD=b"M5_RUN_DONE\n"
FAULT=b"M5_ERR_USER_FAULT\n"
DIRTY=(" movq $2026,%r12\n pushq $0x3f80\n ldmxcsr (%rsp)\n addq $8,%rsp\n"+
       "".join(f" pcmpeqd %xmm{i},%xmm{i}\n" for i in range(16))+
       " fld1; fldpi\n")
# A real FXSAVE64 reads the task's own architectural state only.
CHECK=""" subq $512,%rsp
 fxsave64 (%rsp)
 movq $2026,%r12
 cmpw $0x037f,0(%rsp)
 jne bad
 cmpw $0,2(%rsp)
 jne bad
 cmpb $0,4(%rsp)
 jne bad
 cmpl $0x1f80,24(%rsp)
 jne bad
 leaq 160(%rsp),%rsi
 movl $256,%ecx
1:
 cmpb $0,(%rsi)
 jne bad
 incq %rsi
 decl %ecx
 jnz 1b
 jmp done
bad:
 xorq %r12,%r12
done:
 addq $512,%rsp
"""
# Returning syscall must preserve the running task's own SSE state.
LIVE=REPORT.replace(" movq $2,%rax",""" movq %xmm15,%rax
 cmpq $-1,%rax
 jne lost
 subq $8,%rsp
 stmxcsr (%rsp)
 cmpl $0x3f80,(%rsp)
 leaq 8(%rsp),%rsp
 je intact
lost:
 xorq %r12,%r12
intact:
 movq $2,%rax""",1)

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-sse-context-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        root=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",root)
        for name,body in [("dirtyfx",DIRTY+LIVE),("checkfx",CHECK+REPORT),
                          ("fxfault",DIRTY+" ud2\n")]:
            asm=work/(name+".S")
            asm.write_text(HEADER+body)
            build_image(asm,root/(name+".hke"))
        from test_m5_user_x87_context import CHECK as X87_CHECK
        asm=work/"legacy.S"
        asm.write_text(HEADER+X87_CHECK+REPORT)
        build_image(asm,root/"legacy.hke")
        for timed in (False,True):
            if timed:
                asm=work/"fxspin.S"
                asm.write_text(HEADER+DIRTY+"1: jmp 1b\n")
                build_image(asm,root/"fxspin.hke")
            iso=work/("timed.iso" if timed else "plain.iso")
            (timed_build if timed else plain)(ROOT/"examples/kernel.html",iso,work,cache,"--romfs-root",str(root))
            if not timed:
                log,uart=exercise(iso,[(b"run /legacy.hke\r",GOOD),
                    (b"run /dirtyfx.hke\r",FAULT),(b"run /legacy.hke\r",GOOD),
                    (b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)],HTML,cpu="qemu64,-fxsr,-sse,-sse2")
                for data in (log,uart):
                    assert data.count(b"M5_C_USER_VALUE=2026\n")==2,data
                    assert data.count(b"M5_E_USER_UD\n")==1,data
                print("M5-E3-O no FXSR/SSE CPU legacy x87 + unsupported SSE fault PASS",flush=True)
            cmds=[(b"run /checkfx.hke\r",GOOD),(b"run /dirtyfx.hke\r",GOOD),
                  (b"run /checkfx.hke\r",GOOD),(b"run /fxfault.hke\r",FAULT),
                  (b"run /checkfx.hke\r",GOOD)]
            if timed:
                cmds += [(b"run /fxspin.hke\r",SPIN_TRACE.replace(b"/apps/spin.hke",b"/fxspin.hke")),
                         (b"run /checkfx.hke\r",GOOD)]
            cmds += [(b"run /apps/hello.hke\r",GOOD),(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)]
            for attempt in range(3 if timed else 1):
                log,uart=exercise(iso,cmds,HTML,cpu=CPU if timed else "qemu64")
                for data in (log,uart):
                    assert data.count(b"M5_C_USER_VALUE=2026\n")==5+int(timed) and b"M5_C_USER_VALUE=0\n" not in data,data
                    assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==5+int(timed),data
                    assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==1,data
                    assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data
                print(f"M5-E3-O real XMM0..15/MXCSR fresh state + syscall preservation timed={timed} run={attempt+1} PASS",flush=True)
if __name__=="__main__":main()
