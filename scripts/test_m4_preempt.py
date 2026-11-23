#!/usr/bin/env python3
"""M4-B2 genuine x2APIC timer preemption in QEMU: never-yielding ring-0 tasks."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT

HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M4 PREEMPT HTML MUTATED!\nNative code, not a browser.\n"
PREFIX = "M3_IDT_READY\nM4_X2APIC_TIMER_READY\n"
TASKS = "".join(f"M4_PREEMPT_{label}_{i}\n"
                for i in range(3) for label in "AB")
DONE = "M4_X2APIC_PREEMPT_PASS\nM4_PREEMPT_MAIN_RESTORED\n"

def build(source: Path, iso: Path, work: Path, *,
          masked=False, bad_frame=False):
    args = [sys.executable, str(ROOT / "scripts/build_boot.py"),
            "--source", str(source), "--out", str(iso),
            "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                          str(ROOT / "build/.cache")),
            "--work-dir", str(work), "--test-exit", "--exception-idt",
            "--preempt-probe"]
    if masked:
        args.append("--preempt-timer-mask")
    if bad_frame:
        args.append("--preempt-bad-frame")
    result = subprocess.run(args, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f"M4-B2 ISO builder failure:\n{result.stdout}\n{result.stderr}")

def boot(iso: Path, cpu: str, *, timeout=15):
    cmd = ["qemu-system-x86_64", "-M", "q35", "-cpu", cpu,
           "-smp", "1", "-m", "256M", "-cdrom", str(iso),
           "-boot", "d", "-display", "none", "-serial", "none",
           "-monitor", "none", "-net", "none", "-debugcon", "stdio",
           "-global", "isa-debugcon.iobase=0xe9",
           "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
           "-no-reboot"]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)

def output(result):
    return result.stdout.decode("utf-8", errors="replace")

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-preempt-") as td:
        work = Path(td)
        source = ROOT / "examples/kernel.html"
        normal = work / "normal.iso"
        build(source, normal, work)
        for iteration in range(3):
            result = boot(normal, "qemu64,+x2apic")
            expected = PREFIX + TASKS + DONE + HTML
            assert (result.returncode, output(result)) == (SUCCESS_EXIT, expected), (
                iteration, result.returncode, output(result), result.stderr)
        print("M4 THREE REPEATED QEMU x2APIC PREEMPTION BOOTS PASS")

        changed_source = work / "changed.html"
        original = source.read_text(encoding="utf-8")
        assert original.count("Hello from HTML Kernel!") == 1
        changed_source.write_text(original.replace(
            "Hello from HTML Kernel!", "M4 PREEMPT HTML MUTATED!"),
            encoding="utf-8")
        altered = work / "changed.iso"
        build(changed_source, altered, work)
        result = boot(altered, "qemu64,+x2apic")
        assert (result.returncode, output(result)) == (
            SUCCESS_EXIT, PREFIX + TASKS + DONE + CHANGED), (
            result.returncode, output(result))
        assert normal.read_bytes() != altered.read_bytes()
        assert HTML not in output(result)
        print("M4 REAL QEMU SOURCE-CHANGED ISO AND STALE OUTPUT REJECTION PASS")

        for unsupported_cpu in ("qemu64", "qemu64,-apic"):
            result = boot(normal, unsupported_cpu)
            assert (result.returncode, output(result)) == (
                51, "M3_IDT_READY\nM4_X2APIC_UNSUPPORTED\n"), (
                unsupported_cpu, result.returncode, output(result))
        print("M4 NO-x2APIC AND NO-APIC CPU PROFILES REJECTED WITHOUT HANG")

        bad = work / "bad-frame.iso"
        build(source, bad, work, bad_frame=True)
        result = boot(bad, "qemu64,+x2apic")
        assert (result.returncode, output(result)) == (
            51, "M3_IDT_READY\nM4_PREEMPT_BAD_FRAME_REJECTED\n"), (
            result.returncode, output(result))
        print("M4 MISALIGNED INTERRUPT-STACK CONTEXT REJECTED (REAL QEMU)")

        masked = work / "masked.iso"
        build(source, masked, work, masked=True)
        try:
            result = boot(masked, "qemu64,+x2apic", timeout=4)
        except subprocess.TimeoutExpired as exc:
            observed = (exc.stdout or b"").decode(errors="replace")
            assert observed == PREFIX + "M4_PREEMPT_A_0\n", observed
            print("M4 MASKED APIC TIMER DOES NOT PREEMPT NON-YIELDER")
        else:
            raise AssertionError(
                f"M4 masked timer still allowed scheduling: {result.returncode}, {output(result)}")

        for extra in (["--preempt-probe"],
                      ["--preempt-timer-mask"],
                      ["--preempt-bad-frame"],
                      ["--preempt-probe", "--exception-idt", "--task-probe"],
                      ["--preempt-probe", "--exception-idt", "--paging-probe"]):
            invalid = work / "invalid.iso"
            cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
                   "--source", str(source), "--out", str(invalid), *extra]
            reject = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                    text=True, timeout=15)
            assert reject.returncode != 0 and not invalid.exists(), extra
        print("M4 INCOMPATIBLE/UNSAFE BUILDER FLAGS REJECTED")
    print("M4-B2 TRUE TIMER-DRIVEN RING-0 PREEMPTION E2E PASS")

if __name__ == "__main__":
    main()
