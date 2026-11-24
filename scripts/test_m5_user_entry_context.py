"""M5-E3-K: verify actual fresh CPL3 integer register/flags state."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML
from test_m5_user_timeout import build as build_timer, CPU, SPIN_TRACE
from test_m5_user_fault_recovery import build as build_no_timer
from build_user_image import build as build_image

GOOD=b"M5_RUN_DONE\n"
VALUE=b"M5_C_USER_VALUE=2026\n"
BAD=b"M5_C_USER_VALUE=0\n"
REGS=("rax","rbx","rcx","rdx","rsi","rdi","rbp","r8","r9","r10","r11","r12","r13","r14","r15")

def probe(flags):
    # Capture initial RFLAGS before OR updates status flags. Only inspect
    # our own CPU registers and private stack; never dereference their values.
    return ('.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n pushfq\n'+
            ''.join(f' orq %{reg},%rax\n' for reg in REGS[1:])+
            f' jnz bad\n popq %rax\n cmpq ${flags},%rax\n jne bad_flags\n movq $2026,%r12\n jmp report\nbad:\n addq $8,%rsp\nbad_flags:\n xorq %r12,%r12\nreport:\n movq $0,%rax\n movq $0x1234,%rdi\n int $0x80\n movq $2,%rax\n movq %r12,%rdi\n int $0x80\n movq $1,%rax\n xorq %rdi,%rdi\n int $0x80\n ud2\n.section .note.GNU-stack,"",@progbits\n')

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-entry-context-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        for timed in (False,True):
            root=work/("timer-romfs" if timed else "plain-romfs")
            shutil.copytree(ROOT/"examples/romfs",root)
            asm=work/"entry.S"
            asm.write_text(probe(0x202 if timed else 2))
            build_image(asm,root/"entry.hke")
            iso=work/("timer.iso" if timed else "plain.iso")
            (build_timer if timed else build_no_timer)(ROOT/"examples/kernel.html",iso,work,cache,"--romfs-root",str(root))
            commands=[(b"run /entry.hke\r",GOOD),(b"run /apps/fault-ud.hke\r",b"M5_ERR_USER_FAULT\n"),(b"run /entry.hke\r",GOOD)]
            if timed:
                commands += [(b"run /apps/spin.hke\r",SPIN_TRACE),(b"run /entry.hke\r",GOOD)]
            commands += [(b"run /apps/hello.hke\r",GOOD),(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)]
            for attempt in range(3 if timed else 1):
                log,uart=exercise(iso,commands,HTML,cpu=CPU if timed else None)
                for data in (log,uart):
                    assert data.count(VALUE)==3+int(timed) and BAD not in data,data
                    assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==3+int(timed),data
                    assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==1,data
                    assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data
                print(f"M5-E3-K fresh GPR/RFLAGS and fault/timeout reentry timed={timed} run={attempt+1} PASS",flush=True)

if __name__=="__main__":main()
