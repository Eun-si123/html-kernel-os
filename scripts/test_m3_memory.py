#!/usr/bin/env python3
"""M3 physical memory handoff: host boundary oracle + real QEMU BIOS probe."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

PREFIX = ("M3_MEMMAP_VALIDATED\n"
          "M3_PAGES_WRITTEN\n"
          "M3_EXHAUSTION_HANDLED\n")
KERNEL = "Hello from HTML Kernel!\nNative code, not a browser.\n"
BAD_MAP = "M3_BADMAP_REJECTED\n"
FAULT_EXIT = 39  # QEMU isa-debug-exit with value 0x13


def command(args: list[str], *, timeout: int = 100) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          check=False, timeout=timeout)


def host_oracle(work: Path) -> None:
    for opt in ("-O0", "-O3"):
        binary = work / f"pool-{opt[1:]}"
        args = [
            "gcc", "-std=c11", opt, "-Wall", "-Wextra", "-Werror",
            "-fsanitize=undefined", "-fno-sanitize-recover=all",
            "-I", str(ROOT / "boot"),
            str(ROOT / "boot/page_pool.c"),
            str(ROOT / "tests/native/test_page_pool.c"),
            "-o", str(binary),
        ]
        result = command(args, timeout=30)
        if result.returncode:
            raise AssertionError(f"M3 {opt} host C error: {result.stderr}")
        actual = command([str(binary)], timeout=10)
        if (actual.returncode != 0 or
                actual.stdout != "M3 PAGE POOL HOST CONTRACT PASS\n" or
                actual.stderr):
            raise AssertionError(f"M3 host oracle {opt}: "
                                 f"{actual.returncode}, {actual.stdout!r}, "
                                 f"{actual.stderr!r}")
        print(f"M3 HOST PAGE POOL {opt} UBSAN PASS")


def build_m3(source: Path, iso: Path, cache: Path, work: Path, bad: bool) -> None:
    args = [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(source), "--out", str(iso),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit", "--memory-probe",
    ]
    if bad:
        args.append("--memory-probe-badmap")
    result = command(args, timeout=200)
    if result.returncode:
        raise AssertionError(f"M3 QEMU build failed: {result.stdout}\n{result.stderr}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opts = parser.parse_args()
    opts.work_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/kernel.html"
    original = source.read_text(encoding="utf-8")
    if original.count("Hello from HTML Kernel!") != 1:
        raise AssertionError("base HTML kernel fixture was changed")
    with tempfile.TemporaryDirectory(prefix="htmlk-m3-", dir=opts.work_dir) as td:
        work = Path(td)
        host_oracle(work)
        iso = work / "m3.iso"
        build_m3(source, iso, opts.cache_dir, opts.work_dir, bad=False)
        code, output = boot(iso)
        if code != SUCCESS_EXIT or output != PREFIX + KERNEL:
            raise AssertionError(
                f"M3 actual BIOS QEMU memory probe failed: {code}, {output!r}")
        print("M3 QEMU LIMINE MEMMAP + HHDM READBACK + EXHAUSTION PASS")
        changed = work / "changed.html"
        changed.write_text(original.replace(
            "Hello from HTML Kernel!", "Altered HTML executes after M3 probe!"
        ), encoding="utf-8")
        second = work / "m3-changed.iso"
        build_m3(changed, second, opts.cache_dir, opts.work_dir, bad=False)
        code, output = boot(second)
        expected = PREFIX + KERNEL.replace(
            "Hello from HTML Kernel!", "Altered HTML executes after M3 probe!")
        if code != SUCCESS_EXIT or output != expected:
            raise AssertionError(
                f"M3 modified HTML not executed after probe: {code}, {output!r}")
        if iso.read_bytes() == second.read_bytes():
            raise AssertionError("M3 source mutation failed to change real ISO")
        print("M3 CHANGED-SOURCE PROVENANCE PASS")
        bad_iso = work / "m3-bad-map.iso"
        build_m3(source, bad_iso, opts.cache_dir, opts.work_dir, bad=True)
        code, output = boot(bad_iso)
        if code != FAULT_EXIT or output != BAD_MAP:
            raise AssertionError(
                f"M3 malformed copied map was not rejected: {code}, {output!r}")
        print("M3 QEMU MALFORMED MAP NEGATIVE CONTROL PASS")
    print("M3 INITIAL REAL MEMORY BOOTSTRAP E2E PASS")


if __name__ == "__main__":
    main()
