#!/usr/bin/env python3
"""M4-D1: native QEMU CPL3 timer preemption of never-yielding tasks."""
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT

PREFIX = "M3_TSS_IST_READY\nM3_IDT_READY\nM4_D1_TWO_CPL3_CR3_READY\n"
START = PREFIX + "M4_D1_TIMER_READY\n"
PROGRESS = "".join(f"M4_D1_USER_{t}_{i}\n"
                   for i in range(3) for t in "AB")
FINISH = "M4_D1_CPL3_PREEMPT_PASS\nM4_D1_ALL_FRAMES_RECLAIMED\n"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
ALTERED = "D1 PREEMPT HTML SOURCE CHANGED!\nNative code, not a browser.\n"

def build(source: Path, iso: Path, work: Path, flags=()):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                         str(ROOT / "build/.cache")),
           "--work-dir", str(work), "--test-exit", "--exception-idt",
           "--tss-ist", "--user-preempt-probe", *flags]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    assert result.returncode == 0, (cmd, result.stdout, result.stderr)

def boot(iso: Path, cpu="qemu64,+x2apic", *, timeout=15):
    cmd = ["qemu-system-x86_64", "-M", "q35", "-cpu", cpu, "-smp", "1",
           "-m", "256M", "-cdrom", str(iso), "-boot", "d",
           "-display", "none", "-serial", "none", "-monitor", "none",
           "-net", "none", "-debugcon", "stdio",
           "-global", "isa-debugcon.iobase=0xe9",
           "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
           "-no-reboot"]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True,
                          timeout=timeout)

def txt(r):
    return r.stdout.decode(errors="replace")
def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-d1-") as tmp:
        work = Path(tmp)
        original_source = ROOT / "examples/kernel.html"
        original_iso = work / "preempt.iso"
        build(original_source, original_iso, work)
        for run in range(3):
            result = boot(original_iso)
            assert (result.returncode, txt(result)) == (
                SUCCESS_EXIT, START + PROGRESS + FINISH + HTML), (
                run, result.returncode, txt(result), result.stderr)
        print("M4-D1 THREE REAL CPL3 x2APIC QEMU REPEATED BOOTS PASS")

        html = original_source.read_text(encoding="utf-8")
        assert html.count("Hello from HTML Kernel!") == 1
        changed = work / "changed.html"
        changed.write_text(html.replace("Hello from HTML Kernel!",
                                        "D1 PREEMPT HTML SOURCE CHANGED!"),
                           encoding="utf-8")
        changed_iso = work / "changed.iso"
        build(changed, changed_iso, work)
        result = boot(changed_iso)
        assert (result.returncode, txt(result)) == (
            SUCCESS_EXIT, START + PROGRESS + FINISH + ALTERED), (
            result.returncode, txt(result))
        assert original_iso.read_bytes() != changed_iso.read_bytes()
        assert HTML not in txt(result)
        print("M4-D1 SOURCE HTML -> DIFFERENT ISO -> REAL QEMU OUTPUT PASS")

        for cpu in ("qemu64", "qemu64,-apic"):
            result = boot(original_iso, cpu)
            assert (result.returncode, txt(result)) == (
                57, PREFIX + "M4_D1_NO_X2APIC\n"), (
                cpu, result.returncode, txt(result))
        print("M4-D1 UNSUPPORTED CPU FAILS CLOSED")
        bad_iso = work / "badframe.iso"
        build(original_source, bad_iso, work, ("--user-preempt-bad-frame",))
        result = boot(bad_iso)
        assert (result.returncode, txt(result)) == (
            57, "M3_TSS_IST_READY\nM3_IDT_READY\nM4_D1_BAD_FRAME_REJECTED\n"), (
            result.returncode, txt(result))
        print("M4-D1 FORGED CPL0 SELECTOR REJECTED BEFORE IRET")

        masked_iso = work / "masked.iso"
        build(original_source, masked_iso, work, ("--user-preempt-mask",))
        try:
            result = boot(masked_iso, timeout=4)
        except subprocess.TimeoutExpired as exc:
            log = (exc.stdout or b"").decode(errors="replace")
            assert log == START, log
            print("M4-D1 MASKED TIMER CANNOT SCHEDULE NEVER-YIELDING CPL3")
        else:
            raise AssertionError(
                f"masked timer unexpectedly finished: {result.returncode} {txt(result)}")

        corrupted = work / "corrupt-gpr.iso"
        build(original_source, corrupted, work, ("--user-preempt-corrupt-gpr",))
        r = boot(corrupted)
        expected = (START + "M3_EXCEPTION V=06\n"
                    "M3_RIP=0x[0-9A-F]{16}\n"
                    "M3_ERROR=0x0000000000000000\n")
        assert r.returncode == 45 and re.fullmatch(expected, txt(r)), (
            r.returncode, txt(r))
        print("M4-D1 REAL CPU CHECKS ALL 15 GPR; R15 CORRUPTION PRODUCES #UD")

        wrong_root = work / "wrong-cr3.iso"
        build(original_source, wrong_root, work, ("--user-preempt-bad-cr3",))
        r = boot(wrong_root)
        assert (r.returncode, txt(r)) == (
            57, START + "M4_D1_USER_A_0\nM4_D1_IRQ_CONTEXT_INVALID\n"), (
            r.returncode, txt(r))
        print("M4-D1 WRONG ACTIVE CR3 IS REJECTED IN REAL TIMER IRQ")

        revoked = work / "revoked-code.iso"
        build(original_source, revoked, work, ("--user-preempt-revoke-b",))
        r = boot(revoked)
        pattern = (START + "M4_D1_USER_A_0\nM4_D1_USER_B_0\n"
                   "M4_D1_USER_A_1\nM3_IST_PF_STACK_OK\n"
                   "M3_EXCEPTION V=0E\nM3_RIP=0x(?P<rip>[0-9A-F]{16})\n"
                   "M3_ERROR=0x0000000000000014\n"
                   "M3_CR2=0x(?P<cr2>[0-9A-F]{16})\n")
        observed = re.fullmatch(pattern, txt(r))
        assert r.returncode == 45 and observed, (r.returncode, txt(r))
        assert observed["rip"] == observed["cr2"] and (
            0x400000000000 <= int(observed["cr2"], 16) < 0x400000001000)
        print("M4-D1 REVOKED B EXECUTABLE PTE CAUSES TRUE INSTRUCTION #PF AFTER CR3 FLUSH")

        for extra in (
                ("--user-preempt-corrupt-gpr",),
                ("--user-preempt-bad-cr3",),
                ("--user-preempt-revoke-b",),
                ("--user-preempt-probe",),
                ("--user-preempt-mask",),
                ("--user-preempt-bad-frame",),
                ("--user-preempt-probe", "--exception-idt"),
                ("--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--preempt-probe"),
                ("--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--user-isolation-probe"),
                ("--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--user-preempt-mask", "--user-preempt-bad-frame"),
                ("--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--test-exit", "--user-preempt-corrupt-gpr",
                 "--user-preempt-revoke-b"),
                ("--user-preempt-probe", "--exception-idt", "--tss-ist",
                 "--test-exit", "--user-preempt-fault",
                 "--user-preempt-bad-cr3"),
        ):
            path = work / "invalid.iso"
            r = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--out", str(path), *extra],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            assert r.returncode != 0 and not path.exists(), (extra, r.stderr)
        print("M4-D1 UNSAFE BUILDER COMBINATIONS REJECTED")
    print("M4-D1 REAL INTERRUPT-DRIVEN USER PREEMPTION E2E PASS")

if __name__ == "__main__":
    main()
