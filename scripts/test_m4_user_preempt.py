#!/usr/bin/env python3
"""M4-D actual x2APIC preemption across 2 ring3 CR3s plus surviving CPU fault."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT

PREFIX = ("M3_TSS_IST_READY\nM3_IDT_READY\n"
          "M4_D_USER_ROOTS_READY\nM4_D_TIMER_READY\n")
PROGRESS = "".join(f"M4_D_{name}_{n}\n"
                   for n in range(3) for name in "AB")
AFTER = ("M4_D_A_RECLAIMED\nM4_D_B_AFTER_FAULT_3\n"
         "M4_D_B_AFTER_FAULT_4\nM4_D_RING3_PREEMPT_PASS\n"
         "M4_D_NO_FRAME_LEAK\n")
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M4-D SOURCE MODIFIED!\nNative code, not a browser.\n"

def build(src, iso, work, *, extra=()):
    command = [sys.executable, str(ROOT / "scripts/build_boot.py"),
               "--source", str(src), "--out", str(iso),
               "--work-dir", str(work),
               "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                            str(ROOT / "build/.cache")),
               "--exception-idt", "--tss-ist", "--user-preempt-probe",
               "--test-exit", *extra]
    result = subprocess.run(command, cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, (result.stdout, result.stderr)

def boot(iso, cpu="qemu64,+x2apic", *, timeout=15):
    command = ["qemu-system-x86_64", "-M", "q35", "-cpu", cpu,
               "-smp", "1", "-m", "256M", "-cdrom", str(iso),
               "-boot", "d", "-display", "none", "-serial", "none",
               "-monitor", "none", "-net", "none", "-debugcon", "stdio",
               "-global", "isa-debugcon.iobase=0xe9", "-device",
               "isa-debug-exit,iobase=0xf4,iosize=0x04", "-no-reboot"]
    result = subprocess.run(command, capture_output=True, timeout=timeout)
    return result.returncode, result.stdout.decode(errors="replace")

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-m4-d-") as td:
        work = Path(td)
        source = ROOT / "examples/kernel.html"
        normal = work / "normal.iso"
        build(source, normal, work)
        expected = PREFIX + PROGRESS + "M3_IST_PF_STACK_OK\n" + (
            "M4_D_A_CPU_PF_5\n") + AFTER + HTML
        for iteration in range(3):
            observed = boot(normal)
            assert observed == (SUCCESS_EXIT, expected), (
                "normal", iteration, observed)
        print("M4-D REAL x2APIC CPL3 PREEMPT A/B x3 BOOTS PASS")

        changed_source = work / "changed.html"
        original = source.read_text(encoding="utf-8")
        assert original.count("Hello from HTML Kernel!") == 1
        changed_source.write_text(original.replace(
            "Hello from HTML Kernel!", "M4-D SOURCE MODIFIED!"),
            encoding="utf-8")
        altered = work / "changed.iso"
        build(changed_source, altered, work)
        observed = boot(altered)
        assert observed == (SUCCESS_EXIT, expected.replace(HTML, CHANGED)), observed
        assert normal.read_bytes() != altered.read_bytes()
        assert HTML not in observed[1]
        print("M4-D REAL HTML CHANGE -> DIFFERENT ISO/NATIVE CODE PASS")

        for mode, fault in (("--user-preempt-gp", "M4_D_A_CPU_GP_0\n"),
                            ("--user-preempt-ro",
                             "M3_IST_PF_STACK_OK\nM4_D_A_CPU_PF_7\n")):
            iso = work / (mode[2:] + ".iso")
            build(source, iso, work, extra=(mode,))
            code, out = boot(iso)
            assert (code, out) == (SUCCESS_EXIT, PREFIX + PROGRESS +
                                   fault + AFTER + HTML), (mode, code, out)
            print("M4-D ACTUAL CPL3 CPU FAULT + SURVIVOR:", mode)

        for cpu in ("qemu64", "qemu64,-apic"):
            code, out = boot(normal, cpu)
            assert (code, out) == (55, "M3_TSS_IST_READY\n"
                "M3_IDT_READY\nM4_D_USER_ROOTS_READY\n"
                "M4_D_X2APIC_UNSUPPORTED\n"), (cpu, code, out)
        print("M4-D REJECT UNSUPPORTED x2APIC CPU PROFILES PASS")

        bad_frame = work / "bad-frame.iso"
        build(source, bad_frame, work, extra=("--user-preempt-bad-frame",))
        observed = boot(bad_frame)
        assert observed == (55, "M3_TSS_IST_READY\nM3_IDT_READY\n"
                            "M4_D_MISALIGNED_FRAME_REJECTED\n"), observed
        print("M4-D MALFORMED SAVED CPL3 IRQ FRAME REJECTION PASS")

        masked = work / "masked.iso"
        build(source, masked, work, extra=("--user-preempt-mask",))
        try:
            code, out = boot(masked, timeout=4)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b"").decode(errors="replace")
            assert output == PREFIX, output
            print("M4-D MASKED REAL TIMER BLOCKS NON-YIELDING USER TASK SWITCH PASS")
        else:
            raise AssertionError(f"masked preempt still progressed {code} {out!r}")

        unexpected = work / "unexpected-b.iso"
        build(source, unexpected, work, extra=("--user-preempt-unexpected-b",))
        code, out = boot(unexpected)
        assert code == 45 and re.fullmatch(
            PREFIX + PROGRESS + "M3_IST_PF_STACK_OK\n"
            "M4_D_A_CPU_PF_5\nM4_D_A_RECLAIMED\n"
            "M4_D_B_AFTER_FAULT_3\nM3_EXCEPTION V=0D\n"
            "M3_RIP=0x[0-9A-F]{16}\n"
            "M3_ERROR=0x0000000000000000\n", out), (code, out)
        assert "M4_D_RING3_PREEMPT_PASS" not in out
        print("M4-D UNARMED B GP FAIL-STOPS INSTEAD OF BAD RECOVERY PASS")

        invalid_options = [
            ["--user-preempt-probe"],
            ["--user-preempt-mask"],
            ["--user-preempt-unexpected-b"],
            ["--user-preempt-probe", "--exception-idt"],
            ["--user-preempt-probe", "--exception-idt", "--tss-ist",
             "--user-isolation-probe"],
            ["--user-preempt-probe", "--exception-idt", "--tss-ist",
             "--preempt-probe"],
            ["--user-preempt-probe", "--exception-idt", "--tss-ist",
             "--paging-probe"],
            ["--user-preempt-probe", "--exception-idt", "--tss-ist",
             "--user-preempt-gp", "--user-preempt-ro"],
        ]
        for flags in invalid_options:
            invalid_iso = work / "invalid.iso"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_boot.py"),
                 "--out", str(invalid_iso), *flags], cwd=ROOT,
                capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not invalid_iso.exists(), flags
        print("M4-D UNSAFE/INCOMPATIBLE BUILDER COMBINATIONS REJECTED")
    print("M4-D REAL CPL3 USER PREEMPTION + SURVIVOR FAULT GATE PASS")

if __name__ == "__main__":
    main()
