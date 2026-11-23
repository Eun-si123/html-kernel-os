#!/usr/bin/env python3
"""Real BIOS QEMU multi-page mapping, repeated frame reuse, and genuine #PF."""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

SOURCE = ROOT / "examples/kernel.html"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M3 MULTI PAGE HTML SOURCE!\nNative code, not a browser.\n"
BASE = ("M3_IDT_READY\nM3_PAGING_MAP_OK\nM3_PAGING_ALIAS_OK\n"
        "M3_MULTI_PAGE_RECLAIM_OK\n")
NORMAL = BASE + "M3_PAGING_UNMAPPED\nM3_PAGING_RESTORED\n"


def build(source: Path, dest: Path, cache: Path, work: Path, *,
          fault: bool = False, combined: bool = False) -> None:
    cmd = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(dest),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit", "--paging-probe", "--exception-idt", "--multi-page-test"
    ]
    if fault:
        cmd.append("--multi-page-fault-test")
    if combined:
        cmd.extend([
            "--tss-ist", "--memory-probe", "--paging-recover-test",
            "--owned-frame-test", "--video-console", "--video-test",
        ])
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise AssertionError(f"multi-page image failed: {r.stdout}\n{r.stderr}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opt = parser.parse_args()
    opt.work_dir.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    marker = "Hello from HTML Kernel!"
    if original.count(marker) != 1:
        raise AssertionError("native HTML source fixture changed")
    with tempfile.TemporaryDirectory(prefix="htmlk-multi-page-",
                                     dir=opt.work_dir) as tmp:
        work = Path(tmp)
        normal = work / "normal.iso"
        build(SOURCE, normal, opt.cache_dir, opt.work_dir)
        code, output = boot(normal, timeout=20)
        if code != SUCCESS_EXIT or output != NORMAL + HTML:
            raise AssertionError(f"real QEMU 3x3 multi-page map failed: {code}, {output!r}")
        print("M3 NATIVE THREE 4KiB LEAF ALIASES x THREE OWNER REUSE ROUNDS PASS")

        changed_source = work / "changed.html"
        changed_source.write_text(original.replace(marker, "M3 MULTI PAGE HTML SOURCE!"),
                                  encoding="utf-8")
        changed = work / "changed.iso"
        build(changed_source, changed, opt.cache_dir, opt.work_dir)
        code, output = boot(changed, timeout=20)
        if code != SUCCESS_EXIT or output != NORMAL + CHANGED:
            raise AssertionError(
                f"changed HTML source did not run after multi-page mapping: {code}, {output!r}")
        if normal.read_bytes() == changed.read_bytes():
            raise AssertionError("modified HTML compiled into the same ISO")
        print("M3 MULTI-PAGE MAPPING SOURCE-CHANGED REAL BIOS QEMU PASS")

        revoked = work / "revoked.iso"
        build(SOURCE, revoked, opt.cache_dir, opt.work_dir, fault=True)
        code, output = boot(revoked, timeout=20)
        pattern = (BASE + "M3_EXCEPTION V=0E\n"
                   "M3_RIP=0x[0-9A-F]{16}\n"
                   "M3_ERROR=0x0000000000000000\n"
                   "M3_CR2=0xFFFFA00000002000\n")
        if code != 45 or re.fullmatch(pattern, output) is None:
            raise AssertionError(
                f"unmapped additional 4KiB page was not rejected: {code} {output!r}")
        if "M3_PAGING_UNMAPPED" in output or HTML in output:
            raise AssertionError("revoked alias fault incorrectly continued")
        print("M3 REAL CPU #PF AT REVOKED SECOND 4KiB PAGE PASS")

        combined = work / "combined.iso"
        build(SOURCE, combined, opt.cache_dir, opt.work_dir, combined=True)
        code, output = boot(combined, timeout=30)
        expected = ("M3_TSS_IST_READY\nM3_IDT_READY\n"
                    "M3_MEMMAP_VALIDATED\nM3_PAGES_WRITTEN\nM3_EXHAUSTION_HANDLED\n"
                    "M3_PAGING_MAP_OK\nM3_PAGING_ALIAS_OK\n"
                    "M3_MULTI_PAGE_RECLAIM_OK\nM3_PAGING_UNMAPPED\n"
                    "M3_IST_PF_STACK_OK\nM3_PF_RECOVERED\nM3_PAGING_RETRY_OK\n"
                    "M3_PAGING_RESTORED\nM3_FRAME_OWNERSHIP_OK\n"
                    + HTML + "FB_PIXELS_OK\n")
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"all M3 memory/IST/one-shot fault/video components failed together: "
                f"{code}, {output!r}")
        print("M3 REAL QEMU MULTIPAGE+OWNER+IST+RECOVERY+RGB COMPOSITION PASS")

        for flags in (
            ["--multi-page-test"],
            ["--multi-page-fault-test"],
            ["--paging-probe", "--multi-page-fault-test"],
            ["--paging-probe", "--multi-page-test", "--multi-page-fault-test"],
            ["--paging-probe", "--multi-page-test", "--exception-idt",
             "--multi-page-fault-test", "--test-exit", "--paging-recover-test"],
        ):
            invalid = work / "invalid.iso"
            cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
                   "--source", str(SOURCE), "--out", str(invalid),
                   "--cache-dir", str(opt.cache_dir), "--work-dir", str(opt.work_dir),
                   *flags]
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                    text=True, timeout=15)
            if result.returncode == 0 or invalid.exists():
                raise AssertionError(f"unsafe multimap flags were allowed: {flags}")
        print("M3 INVALID MULTI-MAP/REVOCATION BUILDER CONTROLS PASS")

    print("M3 BOUNDED MULTI-PAGE MAPPING/REUSE CPU FAULT E2E PASS")


if __name__ == "__main__":
    main()
