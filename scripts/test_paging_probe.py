#!/usr/bin/env python3
"""Real QEMU BIOS 4-level paging: private CR3 alias, unmap, real #PF and recovery to HTML."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

BASE_HTML = ROOT / "examples/kernel.html"
PAGING = ("M3_PAGING_MAP_OK\nM3_PAGING_ALIAS_OK\n"
          "M3_PAGING_UNMAPPED\nM3_PAGING_RESTORED\n")
SOURCE = "Hello from HTML Kernel!\nNative code, not a browser.\n"
MUTATED = "PRIVATE PAGING HTML PROVEN!\nNative code, not a browser.\n"
MEMORY = "M3_MEMMAP_VALIDATED\nM3_PAGES_WRITTEN\nM3_EXHAUSTION_HANDLED\n"


def build(source: Path, iso: Path, cache: Path, work: Path, *,
          fault: bool = False, combined: bool = False) -> None:
    args = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(iso),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit", "--paging-probe", "--exception-idt",
    ]
    if fault:
        args.append("--paging-fault-test")
    if combined:
        args.extend(["--memory-probe", "--video-console", "--video-test"])
    result = subprocess.run(args, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f"paging boot image rejected: {result.stdout}\n{result.stderr}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opt = parser.parse_args()
    opt.work_dir.mkdir(parents=True, exist_ok=True)
    original = BASE_HTML.read_text(encoding="utf-8")
    marker = "Hello from HTML Kernel!"
    if original.count(marker) != 1:
        raise AssertionError("baseline source unexpectedly changed")
    with tempfile.TemporaryDirectory(prefix="htmlk-paging-", dir=opt.work_dir) as name:
        work = Path(name)
        native = work / "paging.iso"
        build(BASE_HTML, native, opt.cache_dir, opt.work_dir)
        code, output = boot(native, timeout=20)
        if code != SUCCESS_EXIT or output != "M3_IDT_READY\n" + PAGING + SOURCE:
            raise AssertionError(f"actual QEMU CR3 alias boot failed: {code} {output!r}")
        print("M3 QEMU PRIVATE CR3 ALIAS + UNMAP + RESTORE PASS")

        source = work / "changed.html"
        source.write_text(original.replace(marker, "PRIVATE PAGING HTML PROVEN!"),
                          encoding="utf-8")
        modified = work / "changed.iso"
        build(source, modified, opt.cache_dir, opt.work_dir)
        code, output = boot(modified, timeout=20)
        if code != SUCCESS_EXIT or output != "M3_IDT_READY\n" + PAGING + MUTATED:
            raise AssertionError(f"HTML not executed after CR3 restore: {code} {output!r}")
        if native.read_bytes() == modified.read_bytes():
            raise AssertionError("HTML edit did not change actual paging ISO")
        print("M3 QEMU POST-CR3 SOURCE PROVENANCE PASS")

        unmap = work / "unmap-fault.iso"
        build(BASE_HTML, unmap, opt.cache_dir, opt.work_dir, fault=True)
        code, output = boot(unmap, timeout=20)
        expected = (
            "M3_IDT_READY\nM3_PAGING_MAP_OK\nM3_PAGING_ALIAS_OK\n"
            "M3_PAGING_UNMAPPED\n"
            "M3_EXCEPTION V=0E\n"
            "M3_RIP=0x[0-9A-F]{16}\n"
            "M3_ERROR=0x0000000000000000\n"
            "M3_CR2=0xFFFFA00000000000\n"
        )
        if code != 45 or re.fullmatch(expected, output) is None:
            raise AssertionError(
                f"revoke did not cause authentic #PF: {code} {output!r}")
        if "Hello from HTML Kernel" in output or "M3_PAGING_RESTORED" in output:
            raise AssertionError("fault image incorrectly resumed after invalid mapping")
        print("M3 QEMU REAL POST-UNMAP PAGE FAULT + CR2 REJECTION PASS")

        combined = work / "combined.iso"
        build(BASE_HTML, combined, opt.cache_dir, opt.work_dir, combined=True)
        code, output = boot(combined, timeout=20)
        expected = "M3_IDT_READY\n" + MEMORY + PAGING + SOURCE + "FB_PIXELS_OK\n"
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"IDT + physical pool + CR3 + framebuffer regression: {code} {output!r}")
        print("M3 ALL FOUR NATIVE MEMORY+IDT+FRAMEBUFFER COMPONENTS PASS")

        # Never silently permit a fault injector with no installed IDT.
        bad = work / "should-not-build.iso"
        for flags in (["--paging-fault-test"], ["--paging-probe", "--paging-fault-test"]):
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_boot.py"),
                 "--source", str(BASE_HTML), "--out", str(bad), *flags],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0 or bad.exists() or "--exception-idt" not in proc.stderr:
                raise AssertionError("unguarded paging fault injection was not rejected")
        print("M3 FAULT OPTION NEGATIVE BUILDER CONTRACT PASS")
    print("M3 PRIVATE CR3 MAP/UNMAP REAL QEMU BOOT E2E PASS")


if __name__ == "__main__":
    main()
