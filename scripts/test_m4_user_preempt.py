#!/usr/bin/env python3
"""Native QEMU M4-D: actual x2APIC CPL3 preemption, separate CR3 and fault survival."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT
from test_m4_preempt import boot, output

START = ("M3_TSS_IST_READY\nM3_IDT_READY\n"
         "M4_D_TWO_CR3_READY\nM4_D_X2APIC_READY\n")
TICKS = "".join(f"M4_D_{who}_TICK_{n}\n"
                for n in range(3) for who in "AB")
FAULT = ("M3_IST_PF_STACK_OK\nM4_D_A_PF_ERROR_5\n"
         "M4_D_A_RECLAIMED\n")
FINISH = ("M4_D_B_SYSCALL_OK\nM4_D_B_EXIT_OK\n"
          "M4_D_NO_FRAME_LEAK\n")
ORIGINAL = "Hello from HTML Kernel!\nNative code, not a browser.\n"
MODIFIED = "M4-D REAL HTML MUTATED!\nNative code, not a browser.\n"


def build(source, iso, work, *, negative=None):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                         str(ROOT / "build/.cache")),
           "--work-dir", str(work), "--exception-idt", "--tss-ist",
           "--user-preempt-probe", "--test-exit"]
    if negative:
        cmd.append(negative)
    r = subprocess.run(cmd, cwd=ROOT, text=True,
                       capture_output=True, timeout=180)
    assert r.returncode == 0, r.stdout + "\n" + r.stderr


def check(iso, expected, cpu="qemu64,+x2apic", exit_code=SUCCESS_EXIT,
          times=1):
    for index in range(times):
        r = boot(iso, cpu, timeout=18)
        assert (r.returncode, output(r)) == (exit_code, expected), (
            index, cpu, r.returncode, output(r), r.stderr)


def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-d-") as td:
        work = Path(td)
        source = ROOT / "examples/kernel.html"
        iso = work / "normal.iso"
        build(source, iso, work)
        check(iso, START + TICKS + FAULT + FINISH + ORIGINAL, times=3)
        print("M4-D THREE REPEATED NATIVE QEMU CPL3 PREEMPTION/FALLBACK BOOTS PASS")

        changed_source = work / "changed.html"
        raw = source.read_text(encoding="utf-8")
        assert raw.count("Hello from HTML Kernel!") == 1
        changed_source.write_text(raw.replace(
            "Hello from HTML Kernel!", "M4-D REAL HTML MUTATED!"),
            encoding="utf-8")
        changed = work / "changed.iso"
        build(changed_source, changed, work)
        check(changed, START + TICKS + FAULT + FINISH + MODIFIED)
        assert iso.read_bytes() != changed.read_bytes()
        assert ORIGINAL not in output(boot(changed, "qemu64,+x2apic"))
        print("M4-D CHANGED HTML -> DIFFERENT ISO -> REAL NATIVE OUTPUT PASS")

        for cpu in ("qemu64", "qemu64,-apic"):
            check(iso, "M3_TSS_IST_READY\nM3_IDT_READY\n"
                  "M4_D_TWO_CR3_READY\nM4_D_X2APIC_UNSUPPORTED\n",
                  cpu=cpu, exit_code=57)
        print("M4-D MISSING X2APIC CPU REJECTED WITH FAILURE EXIT")

        forged = work / "forged.iso"
        build(source, forged, work, negative="--user-preempt-forged")
        check(forged, "M3_TSS_IST_READY\nM3_IDT_READY\n"
              "M4_D_FORGED_CPL0_REJECTED\n", exit_code=57)
        print("M4-D FAKE KERNEL SELECTOR REJECTED BEFORE IRQ")

        masked = work / "masked.iso"
        build(source, masked, work, negative="--user-preempt-mask")
        try:
            boot(masked, "qemu64,+x2apic", timeout=4)
        except subprocess.TimeoutExpired as exc:
            observed = (exc.stdout or b"").decode(errors="replace")
            assert observed == START, observed
        else:
            raise AssertionError("Masked x2APIC allowed nonyielding CPL3 progress")
        print("M4-D MASKED TIMER DOES NOT VOLUNTARILY SWITCH CPL3 TASKS")

        unknown = work / "bad-syscall.iso"
        build(source, unknown, work, negative="--user-preempt-bad-syscall")
        check(unknown, START + TICKS + FAULT +
              "M4_D_B_SYSCALL_OK\nM4_D_UNKNOWN_SYSCALL_REJECTED\n",
              exit_code=57)
        print("M4-D UNKNOWN SURVIVOR SYSCALL FAIL-CLOSED")

        b_fault = work / "b-fault.iso"
        build(source, b_fault, work, negative="--user-preempt-b-fault")
        result = boot(b_fault, "qemu64,+x2apic")
        expect = (START + TICKS + FAULT + "M4_D_B_SYSCALL_OK\n"
                  "M3_EXCEPTION V=0D\nM3_RIP=0x[0-9A-F]{16}\n"
                  "M3_ERROR=0x0000000000000000\n")
        assert result.returncode == 45 and re.fullmatch(expect, output(result)), (
            result.returncode, output(result))
        assert "M4_D_B_EXIT_OK" not in output(result)
        print("M4-D B FAULT DOES NOT REUSE A'S FAULT RECOVERY")

        corrupt = work / "corrupt-gpr.iso"
        build(source, corrupt, work, negative="--user-preempt-corrupt-gpr")
        result = boot(corrupt, "qemu64,+x2apic")
        expect = (START + TICKS + "M3_EXCEPTION V=06\n"
                  "M3_RIP=0x[0-9A-F]{16}\nM3_ERROR=0x0000000000000000\n")
        assert result.returncode == 45 and re.fullmatch(expect, output(result)), (
            result.returncode, output(result))
        print("M4-D 15 GPR VALUES CHECKED BY USER CPU AFTER TIMER SWITCHES")

        bad_cr3 = work / "bad-cr3.iso"
        build(source, bad_cr3, work, negative="--user-preempt-bad-cr3")
        check(bad_cr3, START + "M4_D_A_TICK_0\nM4_D_B_TICK_0\n"
              "M4_D_IRQ_BAD_CONTEXT_OR_TIMEOUT\n", exit_code=57)
        print("M4-D WRONG ACTIVE CR3 OWNER REJECTED IN HARDWARE IRQ")

        revoked = work / "revoked-b.iso"
        build(source, revoked, work, negative="--user-preempt-revoke-b")
        result = boot(revoked, "qemu64,+x2apic")
        prefix = (START + "M4_D_A_TICK_0\nM4_D_B_TICK_0\n"
                  "M4_D_A_TICK_1\nM3_IST_PF_STACK_OK\n")
        pattern = (prefix + "M3_EXCEPTION V=0E\nM3_RIP=0x[0-9A-F]{16}\n"
                   "M3_ERROR=0x[0-9A-F]{16}\n"
                   "M3_CR2=0x0000400000000000\n")
        assert result.returncode == 45 and re.fullmatch(pattern, output(result)), (
            result.returncode, output(result))
        assert "M4_D_B_TICK_1" not in output(result)
        print("M4-D B-ONLY REVOKED PTE FAILS AFTER CR3 TLB FLUSH")

        for flags in (
                ["--user-preempt-probe"],
                ["--user-preempt-mask"],
                ["--user-preempt-bad-syscall"],
                ["--user-preempt-corrupt-gpr"],
                ["--user-preempt-bad-cr3"],
                ["--user-preempt-revoke-b"],
                ["--user-preempt-probe", "--exception-idt"],
                ["--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--preempt-probe"],
                ["--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--user-isolation-probe"],
                ["--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--user-preempt-mask", "--user-preempt-b-fault"]):
            invalid = work / "invalid.iso"
            cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
                   "--out", str(invalid), *flags]
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                               text=True, timeout=20)
            assert r.returncode != 0 and not invalid.exists(), flags
        print("M4-D UNSUPPORTED BUILDER COMBINATIONS REJECTED")
    print("M4-D REAL CPU CPL3 TIMER PREEMPTION + FAULT SURVIVOR E2E PASS")


if __name__ == "__main__":
    main()
