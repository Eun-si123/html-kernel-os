#!/usr/bin/env python3
"""True x86 #PF recovery and owned physical-frame reclamation, via BIOS QEMU."""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

SOURCE = ROOT / "examples/kernel.html"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
ALTERED = "ONE SHOT PAGE FAULT RECOVERY WORKED!\nNative code, not a browser.\n"
MEM = "M3_MEMMAP_VALIDATED\nM3_PAGES_WRITTEN\nM3_EXHAUSTION_HANDLED\n"
PROOF = ("M3_IDT_READY\nM3_PAGING_MAP_OK\nM3_PAGING_ALIAS_OK\n"
         "M3_PAGING_UNMAPPED\nM3_PF_RECOVERED\nM3_PAGING_RETRY_OK\n"
         "M3_PAGING_RESTORED\nM3_FRAME_OWNERSHIP_OK\n")


def build(source: Path, iso: Path, cache: Path, work: Path, *,
          bad_page: bool = False, combined: bool = False) -> None:
    flags = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(iso),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit", "--paging-probe", "--exception-idt",
        "--paging-recover-test", "--owned-frame-test",
    ]
    if bad_page:
        flags.extend(["--fault-test", "page"])
    if combined:
        flags.extend(["--memory-probe", "--video-console", "--video-test"])
    r = subprocess.run(flags, cwd=ROOT, capture_output=True, text=True, timeout=200)
    if r.returncode:
        raise AssertionError(f"QEMU recovery image failed to compile: {r.stdout}\n{r.stderr}")


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    a.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opt = a.parse_args()
    opt.work_dir.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    marker = "Hello from HTML Kernel!"
    if original.count(marker) != 1:
        raise AssertionError("base HTML kernel changed unexpectedly")
    with tempfile.TemporaryDirectory(prefix="htmlk-lazy-pf-",
                                     dir=opt.work_dir) as tmp:
        work = Path(tmp)
        standard = work / "normal.iso"
        build(SOURCE, standard, opt.cache_dir, opt.work_dir)
        code, output = boot(standard, timeout=25)
        if code != SUCCESS_EXIT or output != PROOF + HTML:
            raise AssertionError(
                f"real CPU lazy #PF recovery + 16-frame owner test failed: "
                f"exit={code}, output={output!r}")
        print("M3 REAL PAGE FAULT HANDLER RECOVER/IRETQ RESTART + OWNED FRAMES PASS")

        changed = work / "changed.html"
        changed.write_text(original.replace(marker, "ONE SHOT PAGE FAULT RECOVERY WORKED!"),
                           encoding="utf-8")
        altered = work / "changed.iso"
        build(changed, altered, opt.cache_dir, opt.work_dir)
        code, output = boot(altered, timeout=25)
        if code != SUCCESS_EXIT or output != PROOF + ALTERED:
            raise AssertionError(f"mutated source lost after recovery: {code}, {output!r}")
        if standard.read_bytes() == altered.read_bytes():
            raise AssertionError("HTML source change did not change native ISO")
        print("M3 POST-RECOVERY SOURCE PROVENANCE PASS")

        bad = work / "stray-fault.iso"
        build(SOURCE, bad, opt.cache_dir, opt.work_dir, bad_page=True)
        code, output = boot(bad, timeout=25)
        expected = (
            "M3_IDT_READY\nM3_EXCEPTION V=0E\n"
            "M3_RIP=0x[0-9A-F]{16}\n"
            "M3_ERROR=0x0000000000000000\n"
            "M3_CR2=0x0000000040000000\n"
        )
        if code != 45 or re.fullmatch(expected, output) is None:
            raise AssertionError(
                f"unarmed/unexpected fault wrongly recovered: {code} {output!r}")
        print("M3 UNARMED PAGE FAULT FAIL-CLOSED PASS")

        combined = work / "combined.iso"
        build(SOURCE, combined, opt.cache_dir, opt.work_dir, combined=True)
        code, output = boot(combined, timeout=25)
        expected = ("M3_IDT_READY\n" + MEM + PROOF[len("M3_IDT_READY\n"):]
                    + HTML + "FB_PIXELS_OK\n")
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"physical+private paging+recovery+video composition failed: "
                f"{code} {output!r}")
        print("M3 COMBINED REAL MEMORY/PF REPAIR/VIDEO QEMU PASS")

        # Invalid flags cannot quietly turn off safety checks and build a kernel.
        for flags in (
            ["--paging-recover-test"],
            ["--paging-probe", "--paging-recover-test"],
            ["--owned-frame-test"],
            ["--paging-probe", "--exception-idt", "--paging-fault-test",
             "--paging-recover-test"],
        ):
            dest = work / "unapproved.iso"
            r = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--source", str(SOURCE), "--out", str(dest),
                "--cache-dir", str(opt.cache_dir), "--work-dir", str(opt.work_dir),
                *flags
            ], cwd=ROOT, capture_output=True, text=True, timeout=20)
            if r.returncode == 0 or dest.exists():
                raise AssertionError(f"invalid unsafe flags built an ISO: {flags}")
        print("M3 RECOVERY/MUTEX/OWNERSHIP NEGATIVE BUILD CONTROLS PASS")

    print("M3 BOUNDED RECOVERABLE PAGE FAULT + FRAME OWNERSHIP REAL BIOS E2E PASS")


if __name__ == "__main__":
    main()
