#!/usr/bin/env python3
"""M4-B1: actual PIT IRQ0 drives two cooperative ring-0 task stacks."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT

TASKS = "".join(f"M4_TASK_{name}_{round}\n"
                for round in range(3) for name in "AB")
PREFIX = "M3_IDT_READY\nM4_TIMER_READY\n"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M4 IRQ SOURCE MODIFIED!\nNative code, not a browser.\n"

def build(source, iso, work, *, masked=False):
    args = [sys.executable, str(ROOT / "scripts/build_boot.py"),
            "--source", str(source), "--out", str(iso),
            "--work-dir", str(work),
            "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                         str(ROOT / "build/.cache")),
            "--test-exit", "--exception-idt", "--task-probe", "--timer-probe"]
    if masked:
        args.append("--timer-mask-test")
    result = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise AssertionError(result.stdout + "\n" + result.stderr)

def qemu(iso, *, no_apic, timeout=15):
    args = ["qemu-system-x86_64", "-M", "q35", "-m", "256M"]
    if no_apic:
        args.extend(["-cpu", "qemu64,-apic"])
    args.extend(["-cdrom", str(iso), "-boot", "d", "-display", "none",
                 "-serial", "none", "-monitor", "none", "-net", "none",
                 "-debugcon", "stdio", "-global", "isa-debugcon.iobase=0xe9",
                 "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
                 "-no-reboot"])
    return subprocess.run(args, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)

def decoded(result):
    return result.stdout.decode(errors="replace")

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-timer-") as td:
        root = Path(td)
        for optimization in ("-O0", "-O3"):
            binary = root / ("pit-host-" + optimization)
            subprocess.run([
                "gcc", "-std=c11", optimization, "-march=x86-64",
                "-mgeneral-regs-only", "-fsanitize=undefined",
                "-fno-sanitize-recover=all", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "boot"), str(ROOT / "boot/timer_irq.c"),
                str(ROOT / "tests/native/test_pit_divisor.c"), "-o",
                str(binary)], check=True, timeout=30)
            result = subprocess.run([str(binary)], check=True,
                                    capture_output=True, text=True, timeout=10)
            assert result.stdout == "M4 PIT RATE VALIDATION PASS\n"
        print("M4 PIT -O0/-O3 UBSAN RATE VALIDATION PASS")

        source = ROOT / "examples/kernel.html"
        normal = root / "normal.iso"
        build(source, normal, root)
        result = qemu(normal, no_apic=True)
        expected = PREFIX + TASKS + "M4_TASKS_DONE\nM4_TIMER_IRQ_PASS\n" + HTML
        assert (result.returncode, decoded(result)) == (SUCCESS_EXIT, expected), (
            result.returncode, decoded(result), result.stderr)
        print("M4 REAL PIC/PIT IRQ0 PACES TWO STACKS IN Q35 NO-APIC PASS")

        modified = root / "modified.html"
        original = source.read_text()
        assert original.count("Hello from HTML Kernel!") == 1
        modified.write_text(original.replace("Hello from HTML Kernel!",
                                             "M4 IRQ SOURCE MODIFIED!"))
        altered = root / "altered.iso"
        build(modified, altered, root)
        result = qemu(altered, no_apic=True)
        assert (result.returncode, decoded(result)) == (
            SUCCESS_EXIT, PREFIX + TASKS + "M4_TASKS_DONE\nM4_TIMER_IRQ_PASS\n" +
            CHANGED), (result.returncode, decoded(result))
        assert normal.read_bytes() != altered.read_bytes()
        print("M4 IRQ-DRIVEN HTML SOURCE-MUTATION/STALENESS REJECTION PASS")

        unsupported = qemu(normal, no_apic=False)
        assert (unsupported.returncode, decoded(unsupported)) == (
            49, "M3_IDT_READY\nM4_TIMER_APIC_UNSUPPORTED\n"), (
            unsupported.returncode, decoded(unsupported))
        print("M4 UNSUPPORTED LOCAL APIC FAIL-CLOSED (NO HANG) PASS")

        masked = root / "masked.iso"
        build(source, masked, root, masked=True)
        try:
            result = qemu(masked, no_apic=True, timeout=4)
        except subprocess.TimeoutExpired as timeout:
            observed = (timeout.stdout or b"").decode(errors="replace")
            assert observed == PREFIX, observed
            print("M4 REAL PIC IRQ0 MASK STOPS PROGRESS (NEGATIVE) PASS")
        else:
            raise AssertionError(f"masked IRQ0 unexpectedly finished: {result.returncode}, {decoded(result)}")

        for extras in (["--timer-probe"], ["--timer-mask-test"]):
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--source", str(source), "--out", str(root / "invalid.iso"),
                *extras], capture_output=True, text=True, timeout=15)
            assert result.returncode != 0
        print("M4 INVALID BUILDER OPTIONS REJECTED")
    print("M4-B1 REAL TIMER INTERRUPT ACCOUNTING PROOF PASS")

if __name__ == "__main__":
    main()
