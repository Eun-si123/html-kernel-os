"""M5-F6: true signed numeric reports, shared budget and legacy ABI denial."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT, boot
from test_m5_html_user_text import build as build_iso
from test_m5_interactive_run import exercise, HTML
from test_m5_user_timeout import CPU, SPIN_TRACE
from test_m5_user_loader import make_iso as legacy_iso
from build_user_image import build as build_assembly

APP = ROOT/"examples/user-programs/html-i64-report.html"
VALUES = [-2147483648,-7,-9223372036854775808,9223372036854775807,0,18446744073709551615]
GOOD=b"M5_RUN_DONE\n"
ERR=b"M5_ERR_USER_SYSCALL\n"

def values(data):
    prefix=b"M5_C_USER_VALUE="
    return [int(line[len(prefix):]) for line in data.splitlines() if line.startswith(prefix)]

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-f6-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        root=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",root)
        kernel=ROOT/"examples/kernel.html"
        # Alternate signed and unsigned reports, then exceed the shared cap.
        asm=work/"budget.S"
        asm.write_text('.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n movq $0,%rax\n movq $0x1234,%rdi\n int $0x80\n'+
                       ''.join(f' movq ${4 if i%2==0 else 2},%rax\n movq $-1,%rdi\n int $0x80\n' for i in range(9))+
                       ' ud2\n.section .note.GNU-stack,"",@progbits\n')
        build_assembly(asm,root/"mixed-budget.hke")
        iso=work/"original.iso"
        build_iso(kernel,APP,iso,work,cache,root)
        end=(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)
        for attempt in range(3):
            log,uart=exercise(iso,[(b"run /apps/hello.hke\r",GOOD),
                                  (b"run /mixed-budget.hke\r",ERR),
                                  (b"run /apps/spin.hke\r",SPIN_TRACE),
                                  (b"run /apps/hello.hke\r",GOOD),end],HTML,cpu=CPU)
            for data in (log,uart):
                assert values(data)==VALUES+[-1,18446744073709551615]*4+VALUES,data
                assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==2,data
                assert data.count(b"M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n")==1,data
                assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==1,data
            print(f"M5-F6 signed extrema, mixed cap, timeout and rerun {attempt+1}/3 PASS",flush=True)
        changed=work/"changed.html"
        changed.write_text(APP.read_text().replace("negative(7)","negative(9)"))
        changed_iso=work/"changed.iso"
        build_iso(kernel,changed,changed_iso,work,cache,root)
        log,uart=exercise(changed_iso,[(b"run /apps/hello.hke\r",GOOD),end],HTML,cpu=CPU)
        expected=VALUES.copy();expected[1]=-9
        assert values(log)==values(uart)==expected,(log,uart)
        assert changed_iso.read_bytes()!=iso.read_bytes()
        legacy=work/"legacy.iso"
        legacy_iso(kernel,legacy,work,cache,"--user-app-source",str(asm))
        code,raw=boot(legacy,timeout=20)
        assert code==53 and "M4_UNKNOWN_SYSCALL_REJECTED" in raw and "M5_C_USER_VALUE=" not in raw,(code,raw)
        print("M5-F6 mutation and legacy signed syscall denial PASS",flush=True)

if __name__=="__main__":main()
