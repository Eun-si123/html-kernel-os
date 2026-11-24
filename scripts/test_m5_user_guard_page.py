"""M5-E3-J: actual user nonpresent data fault with bad saved RSP."""
import os
from pathlib import Path
import shutil
import tempfile
from test_boot import ROOT, boot
from test_m5_interactive_run import exercise, HTML
from test_m5_user_timeout import build as build_timer, CPU, SPIN_TRACE
from test_m5_user_fault_recovery import build as build_no_timer
from test_m5_user_loader import make_iso as make_legacy
from build_user_image import build as build_image

MARKERS = [b"M5_E3_USER_PF4_GUARD_BAD_RSP_RETIRED\n", b"M5_E3_USER_PF6_GUARD_BAD_RSP_RETIRED\n"]
FAULT=b"M5_ERR_USER_FAULT\n"
APP=ROOT/"examples/user-programs/html-message.html"

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-guard-pf-") as td:
        work=Path(td)
        cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
        romfs=work/"romfs"
        shutil.copytree(ROOT/"examples/romfs",romfs)
        for name,address,op in [("read",0x400000002000,"movq (%rax),%rax"),("write",0x400000002ff8,"movq $1,(%rax)"),("outside",0x400000005000,"movq (%rax),%rax")]:
            src=work/f"{name}.S"
            src.write_text(f'.section .text\n.global htmlk_user_program_start\nhtmlk_user_program_start:\n xorq %rsp,%rsp\n movabsq ${address:#x},%rax\n {op}\n ud2\n.section .note.GNU-stack,"",@progbits\n')
            build_image(src,romfs/f"guard-{name}.hke")
        plain=work/"plain.iso"
        build_no_timer(ROOT/"examples/kernel.html",plain,work,cache,"--romfs-root",str(romfs),"--user-app-html",str(APP))
        commands=[]
        for name in ("read","write"):
            commands.extend([(f"run /guard-{name}.hke\r".encode(),FAULT),(b"run /apps/hello.hke\r",b"M5_RUN_DONE\n")])
        exit_command=(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)
        for iso,cpu,repeats in [(plain,None,1)]:
            out,uart=exercise(iso,commands+[exit_command],HTML,cpu=cpu)
            verify(out,uart,False)
        try:
            exercise(plain,[(b"run /guard-outside.hke\r",FAULT)],HTML)
        except AssertionError as exc:
            assert "'early exit', 45" in str(exc) and "V=0E" in str(exc),str(exc)
        else:
            raise AssertionError("outside guard page must remain fatal")
        (romfs/"guard-outside.hke").unlink()
        timed=work/"timed.iso"
        build_timer(ROOT/"examples/kernel.html",timed,work,cache,"--romfs-root",str(romfs),"--user-app-html",str(APP))
        for i in range(3):
            out,uart=exercise(timed,commands+[(b"run /apps/spin.hke\r",SPIN_TRACE), (b"run /apps/hello.hke\r",b"M5_RUN_DONE\n"),exit_command],HTML,cpu=CPU)
            verify(out,uart,True)
            print(f"M5-E3-J x2APIC guard faults and healthy reruns {i+1}/3 PASS",flush=True)
        legacy=work/"legacy.iso"
        make_legacy(ROOT/"examples/kernel.html",legacy,work,cache,"--user-app-source",str(work/"read.S"))
        code,out=boot(legacy,timeout=20)
        assert code==45 and "M3_EXCEPTION V=0E" in out,(code,out)
        print("M5-E3-J no timer, outside guard and legacy fail-stop controls PASS",flush=True)

def verify(out,uart,timed):
    for data in (out,uart):
        for marker in MARKERS:
            assert data.count(marker)==1,data
        assert data.count(FAULT)==2,data
        assert data.count(b"M5_E_FAULT_FRAMES_RECLAIMED\n")==2,data
        assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==2+int(timed),data
        assert data.count(b"M3_IST_PF_STACK_OK\n")==2,data
        assert data.count(b"M5_E2_TIMEOUT_FRAMES_RECLAIMED\n")==int(timed),data

if __name__=="__main__":
    main()
