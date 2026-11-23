#!/usr/bin/env python3
"""M4-D: actual QEMU x2APIC preemption of two isolated CPL3 non-yielding tasks."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT

BASE=("M3_TSS_IST_READY\nM3_IDT_READY\n"
      "M4_D_TWO_USER_CR3_READY\nM4_D_X2APIC_READY\n")
TASKS="".join(f"M4_D_{which}_{round}\n"
              for round in range(3) for which in "AB")
AFTER=("M3_IST_PF_STACK_OK\nM4_D_A_USER_PF_CONTAINED\n"
       "M4_D_A_FRAMES_RELEASED\nM4_D_B_SURVIVED_FAULT\n"
       "M4_D_B_CPL3_EXIT_OK\nM4_D_ISOLATED_PREEMPTION_PASS\n")
HTML="Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED="M4-D CHANGED HTML EXECUTING!\nNative code, not a browser.\n"
START="M3_TSS_IST_READY\nM3_IDT_READY\n"
def build(source, output, work, extra=None):
    cmd=[sys.executable,str(ROOT/"scripts/build_boot.py"),
         "--source",str(source),"--out",str(output),
         "--cache-dir",os.environ.get("HTMLK_CACHE_DIR",
            str(ROOT/"build/.cache")),"--work-dir",str(work),
         "--test-exit","--exception-idt","--tss-ist",
         "--user-preempt-probe"]
    if extra:
        cmd.append("--user-preempt-"+extra)
    result=subprocess.run(cmd,capture_output=True,text=True,
                          cwd=ROOT,timeout=180)
    if result.returncode:
        raise AssertionError(result.stdout+"\n"+result.stderr)
def boot(iso, cpu="qemu64,+x2apic", timeout=15):
    cmd=["qemu-system-x86_64","-M","q35","-cpu",cpu,"-smp","1",
         "-m","256M","-cdrom",str(iso),"-boot","d","-display",
         "none","-serial","none","-monitor","none","-net","none",
         "-debugcon","stdio","-global","isa-debugcon.iobase=0xe9",
         "-device","isa-debug-exit,iobase=0xf4,iosize=0x04","-no-reboot"]
    return subprocess.run(cmd,capture_output=True,timeout=timeout)
def stdout(result):
    return result.stdout.decode("utf-8",errors="replace")
def require(result,code,output):
    assert (result.returncode,stdout(result))==(code,output), (
        result.returncode,stdout(result),result.stderr)
def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-m4d-") as tmp:
        work=Path(tmp)
        source=ROOT/"examples/kernel.html"
        iso=work/"normal.iso"
        build(source,iso,work)
        for n in range(3):
            require(boot(iso),SUCCESS_EXIT,BASE+TASKS+AFTER+HTML)
        print("M4-D REAL RING3 TWO-CR3 x2APIC PREEMPTION 3x QEMU PASS")

        src=source.read_text(encoding="utf-8")
        assert src.count("Hello from HTML Kernel!")==1
        alternate=work/"changed.html"
        alternate.write_text(src.replace("Hello from HTML Kernel!",
            "M4-D CHANGED HTML EXECUTING!"),encoding="utf-8")
        changed=work/"changed.iso"
        build(alternate,changed,work)
        require(boot(changed),SUCCESS_EXIT,BASE+TASKS+AFTER+CHANGED)
        assert iso.read_bytes()!=changed.read_bytes()
        assert HTML not in stdout(boot(changed))
        print("M4-D REAL HTML MUTATION AFFECTS ISO AND NATIVE CPU OUTPUT")

        for unsupported in ("qemu64","qemu64,-apic"):
            require(boot(iso,cpu=unsupported),57,
                START+"M4_D_TWO_USER_CR3_READY\nM4_D_X2APIC_UNSUPPORTED\n")
        print("M4-D NO-x2APIC AND NO-APIC CPU FAIL CLOSED")

        for neg,marker in (("bad-frame","M4_D_BAD_USER_FRAME_REJECTED\n"),
                           ("wrong-cr3","M4_D_BAD_CR3_REJECTED\n")):
            name=work/(neg+".iso")
            build(source,name,work,extra=neg)
            require(boot(name),57,START+marker)
        print("M4-D FORGED SELECTOR AND DUPLICATE CR3 OWNER REJECTED")

        wrong=work/"wrong-fault.iso"
        build(source,wrong,work,extra="wrong-fault")
        result=boot(wrong)
        exp=(BASE+TASKS+"M3_IST_PF_STACK_OK\n"
             "M3_EXCEPTION V=0E\nM3_RIP=0x[0-9A-F]{16}\n"
             "M3_ERROR=0x0000000000000005\n"
             "M3_CR2=0xFFFFFFFF80002000\n")
        assert result.returncode==45 and re.fullmatch(exp,stdout(result)),(
            result.returncode,stdout(result))
        print("M4-D DIFFERENT USER CR2 CANNOT CLAIM FAULT RECOVERY")

        bad_b=work/"bad-survivor.iso"
        build(source,bad_b,work,extra="bad-survivor")
        result=boot(bad_b)
        exp=(BASE+"M4_D_A_0\nM3_IST_PF_STACK_OK\n"
             "M3_EXCEPTION V=0E\nM3_RIP=0x[0-9A-F]{16}\n"
             "M3_ERROR=0x0000000000000005\n"
             "M3_CR2=0xFFFFFFFF80001000\n")
        assert result.returncode==45 and re.fullmatch(exp,stdout(result)),(
            result.returncode,stdout(result))
        print("M4-D UNEXPECTED SURVIVOR #PF FAILS CLOSED")

        masked=work/"masked.iso"
        build(source,masked,work,extra="timer-mask")
        try:
            got=boot(masked,timeout=4)
        except subprocess.TimeoutExpired as exc:
            text=(exc.stdout or b"").decode(errors="replace")
            assert text==BASE,text
            print("M4-D MASKED x2APIC TIMER CANNOT SWITCH USER TASKS")
        else:
            raise AssertionError((got.returncode,stdout(got)))
        for flags in (
             ["--user-preempt-probe"],
             ["--user-preempt-timer-mask"],
             ["--user-preempt-probe","--tss-ist"],
             ["--user-preempt-probe","--exception-idt"],
             ["--user-preempt-probe","--exception-idt","--tss-ist","--paging-probe"],
             ["--user-preempt-probe","--exception-idt","--tss-ist","--preempt-probe"],
             ["--user-preempt-probe","--exception-idt","--tss-ist",
                "--user-preempt-wrong-fault","--user-preempt-bad-survivor"]):
            dest=work/"bad-option.iso"
            bad=subprocess.run([sys.executable,str(ROOT/"scripts/build_boot.py"),
                "--out",str(dest),*flags],cwd=ROOT,capture_output=True,
                text=True,timeout=15)
            assert bad.returncode!=0 and not dest.exists(),flags
        print("M4-D UNSAFE BUILDER CONFIGURATIONS REJECTED")
    print("M4-D REAL RING3 PREEMPTION/FAULT SURVIVOR FULL E2E PASS")
if __name__=="__main__":
    main()
