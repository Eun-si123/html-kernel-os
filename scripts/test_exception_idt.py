#!/usr/bin/env python3
"""M3 native real-CPU exception proof: 4 fault vectors, normal HTML and combined probes."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

SOURCE = ROOT / "examples/kernel.html"
NORMAL = "M3_IDT_READY\nHello from HTML Kernel!\nNative code, not a browser.\n"
MODIFIED = "M3_IDT_READY\nHTML compiled AFTER IDT install!\nNative code, not a browser.\n"
FAULT_EXIT = 45
FAULTS = {
    "ud": (6, None),
    "page": (14, "0000000040000000"),
    "divide": (0, None),
    "general": (13, None),
}


def build(source: Path, iso: Path, cache: Path, work: Path, *,
          fault: str | None = None, combine: bool = False) -> None:
    command = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(iso),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--exception-idt", "--test-exit",
    ]
    if fault is not None:
        command.extend(["--fault-test", fault])
    if combine:
        command.extend(["--memory-probe", "--video-console", "--video-test"])
    result = subprocess.run(command, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise AssertionError(
            f"M3 {fault or 'normal'} build failed: {result.stdout}\n{result.stderr}"
        )


def fault_output(name: str, output: str, code: int) -> None:
    vector, address = FAULTS[name]
    expect = (
        "M3_IDT_READY\n"
        f"M3_EXCEPTION V={vector:02X}\n"
        "M3_RIP=0x[0-9A-F]{16}\n"
        "M3_ERROR=0x[0-9A-F]{16}\n"
    )
    if address is not None:
        expect += f"M3_CR2=0x{address}\n"
    if code != FAULT_EXIT or re.fullmatch(expect, output) is None:
        raise AssertionError(
            f"real CPU {name} exception not handled by IDT: exit={code}, "
            f"received={output!r}, regex={expect!r}"
        )
    error = re.search(r"M3_ERROR=0x([0-9A-F]{16})", output)
    if error is None or int(error.group(1), 16) != 0:
        raise AssertionError(f"{name} exception error code not zero: {output!r}")
    if "Hello from HTML Kernel" in output:
        raise AssertionError("faulting native image wrongly continued into HTML code")
    print(f"M3 REAL CPU EXCEPTION #{vector:02X} ({name}) FAIL-STOP PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    marker = "Hello from HTML Kernel!"
    if original.count(marker) != 1:
        raise AssertionError("baseline HTML fixture changed")
    with tempfile.TemporaryDirectory(prefix="htmlk-exceptions-",
                                     dir=args.work_dir) as directory:
        work = Path(directory)
        first = work / "normal.iso"
        build(SOURCE, first, args.cache_dir, args.work_dir)
        code, output = boot(first)
        if code != SUCCESS_EXIT or output != NORMAL:
            raise AssertionError(
                f"normal post-IDT HTML boot failed: {code} {output!r}"
            )
        modified = work / "modified.html"
        modified.write_text(original.replace(marker, "HTML compiled AFTER IDT install!"),
                            encoding="utf-8")
        second = work / "modified.iso"
        build(modified, second, args.cache_dir, args.work_dir)
        code, output = boot(second)
        if code != SUCCESS_EXIT or output != MODIFIED:
            raise AssertionError(
                f"source-derived HTML not executed after IDT: {code} {output!r}"
            )
        if first.read_bytes() == second.read_bytes():
            raise AssertionError("HTML source mutation did not change real ISO")
        print("M3 IDT NORMAL + CHANGED HTML QEMU BOOT PASS")

        for fault in FAULTS:
            iso = work / f"{fault}.iso"
            build(SOURCE, iso, args.cache_dir, args.work_dir, fault=fault)
            code, output = boot(iso)
            fault_output(fault, output, code)
            if iso.read_bytes() == first.read_bytes():
                raise AssertionError(f"{fault} fault ISO identical to normal ISO")

        both = work / "combined.iso"
        build(SOURCE, both, args.cache_dir, args.work_dir, combine=True)
        code, output = boot(both)
        expected = (
            "M3_IDT_READY\n"
            "M3_MEMMAP_VALIDATED\nM3_PAGES_WRITTEN\n"
            "M3_EXHAUSTION_HANDLED\n"
            "Hello from HTML Kernel!\nNative code, not a browser.\n"
            "FB_PIXELS_OK\n"
        )
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"combined IDT+map+real framebuffer boot failed: {code} {output!r}"
            )
        print("M3 COMBINED IDT + LIMINE MAP + VIDEO FRAMEBUFFER PASS")

    print("M3 EXCEPTION IDT REAL BIOS QEMU E2E PASS")


if __name__ == "__main__":
    main()
