#!/usr/bin/env python3
"""Actual x86-64 TSS + IST stack delivery for #PF, #DF and recoverable paging."""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

SOURCE = ROOT / "examples/kernel.html"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
MUTATED = "TSS IST SOURCE BOOT PROVEN!\nNative code, not a browser.\n"
READY = "M3_TSS_IST_READY\nM3_IDT_READY\n"


def build(source: Path, out: Path, cache: Path, work: Path, *,
          mode: str = "normal") -> None:
    flags = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(out),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit", "--exception-idt", "--tss-ist",
    ]
    if mode == "pf":
        flags.extend(["--fault-test", "page"])
    elif mode == "df":
        flags.append("--double-fault-test")
    elif mode == "combined":
        flags.extend([
            "--memory-probe", "--paging-probe", "--paging-recover-test",
            "--owned-frame-test", "--video-console", "--video-test",
        ])
    elif mode != "normal":
        raise ValueError(f"invalid test mode: {mode}")
    result = subprocess.run(flags, cwd=ROOT, capture_output=True,
                            text=True, timeout=200)
    if result.returncode:
        raise AssertionError(
            f"M3 IST {mode} image not built: {result.stdout}\n{result.stderr}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    marker = "Hello from HTML Kernel!"
    if original.count(marker) != 1:
        raise AssertionError("source fixture changed")
    with tempfile.TemporaryDirectory(prefix="htmlk-ist-", dir=args.work_dir) as temp:
        work = Path(temp)
        normal = work / "normal.iso"
        build(SOURCE, normal, args.cache_dir, args.work_dir)
        code, output = boot(normal, timeout=20)
        if code != SUCCESS_EXIT or output != READY + HTML:
            raise AssertionError(
                f"TSS+IST startup broke original HTML: {code} {output!r}")
        modified = work / "changed.html"
        modified.write_text(original.replace(marker, "TSS IST SOURCE BOOT PROVEN!"),
                            encoding="utf-8")
        changed = work / "changed.iso"
        build(modified, changed, args.cache_dir, args.work_dir)
        code, output = boot(changed, timeout=20)
        if code != SUCCESS_EXIT or output != READY + MUTATED:
            raise AssertionError(
                f"TSS + IST changed HTML not executed: {code} {output!r}")
        if normal.read_bytes() == changed.read_bytes():
            raise AssertionError("TSS images identical after genuine source change")
        print("M3 TSS/IST NORMAL + SOURCE MUTATION QEMU PASS")

        pf = work / "page-fault.iso"
        build(SOURCE, pf, args.cache_dir, args.work_dir, mode="pf")
        code, output = boot(pf, timeout=20)
        pattern = (READY + "M3_IST_PF_STACK_OK\n"
                   "M3_EXCEPTION V=0E\nM3_RIP=0x[0-9A-F]{16}\n"
                   "M3_ERROR=0x0000000000000000\n"
                   "M3_CR2=0x0000000040000000\n")
        if code != 45 or re.fullmatch(pattern, output) is None:
            raise AssertionError(
                f"actual #PF did not enter IST2: {code} {output!r}")
        print("M3 REAL CPU PAGE FAULT ON IST2 STACK PASS")

        double = work / "double-fault.iso"
        build(SOURCE, double, args.cache_dir, args.work_dir, mode="df")
        code, output = boot(double, timeout=20)
        pattern = (READY + "M3_IST_DF_STACK_OK\n"
                   "M3_EXCEPTION V=08\nM3_RIP=0x[0-9A-F]{16}\n"
                   "M3_ERROR=0x0000000000000000\n")
        if code != 45 or re.fullmatch(pattern, output) is None:
            raise AssertionError(
                f"real CPU #DF did not enter emergency IST1: {code} {output!r}")
        print("M3 REAL DOUBLE FAULT VIA FAILED IST2 DELIVERY ON IST1 PASS")

        combined = work / "combined.iso"
        build(SOURCE, combined, args.cache_dir, args.work_dir, mode="combined")
        code, output = boot(combined, timeout=25)
        expected = (READY + "M3_MEMMAP_VALIDATED\nM3_PAGES_WRITTEN\n"
                    "M3_EXHAUSTION_HANDLED\nM3_PAGING_MAP_OK\n"
                    "M3_PAGING_ALIAS_OK\nM3_PAGING_UNMAPPED\n"
                    "M3_IST_PF_STACK_OK\nM3_PF_RECOVERED\n"
                    "M3_PAGING_RETRY_OK\nM3_PAGING_RESTORED\n"
                    "M3_FRAME_OWNERSHIP_OK\n" + HTML + "FB_PIXELS_OK\n")
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"all M3 components on IST2 did not compose: {code} {output!r}")
        print("M3 IST2 + REAL CPU IRETQ + OWNED PAGES + FRAMEBUFFER PASS")

        bad = work / "invalid-options.iso"
        for flags in (
            ["--tss-ist"],
            ["--double-fault-test"],
            ["--tss-ist", "--exception-idt", "--double-fault-test"],
            ["--tss-ist", "--exception-idt", "--double-fault-test",
             "--test-exit", "--fault-test", "ud"],
        ):
            proc = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--source", str(SOURCE), "--out", str(bad),
                "--cache-dir", str(args.cache_dir), "--work-dir", str(args.work_dir),
                *flags
            ], cwd=ROOT, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0 or bad.exists():
                raise AssertionError(f"unsafe TSS/IST flags accepted: {flags}")
        print("M3 TSS/IST UNSAFE BUILD NEGATIVE OPTIONS PASS")

    print("M3 TSS/IST REAL QEMU EXCEPTION STACK E2E PASS")


if __name__ == "__main__":
    main()
