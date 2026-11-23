#!/usr/bin/env python3
"""Actual x86-64 BIOS QEMU source-derived native framebuffer readback proof."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, SUCCESS_EXIT, boot

SOURCE = ROOT / "examples/framebuffer-kernel.html"
EXPECTED = ("HTML KERNEL ON-SCREEN\n"
            "THE DISPLAY IS DRAWN BY THE BOOTED CPU\n"
            "42\nVIDEO PASS\nFB_PIXELS_OK\n")
MUTATED = ("HTML KERNEL ON-SCREEN\n"
           "THE DISPLAY IS DRAWN BY THE BOOTED CPU\n"
           "43\nVIDEO PASS\nFB_PIXELS_OK\n")


def build(source: Path, iso: Path, cache: Path, work: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_boot.py"),
         "--source", str(source), "--out", str(iso),
         "--cache-dir", str(cache), "--work-dir", str(work),
         "--test-exit", "--video-console", "--video-test"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=180,
    )
    if result.returncode:
        raise AssertionError(f"framebuffer image rejected: {result.stdout}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    p.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = p.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    marker = 'value="6 * 7"'
    if original.count(marker) != 1:
        raise AssertionError("video source fixture changed unexpectedly")
    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-video-") as td:
        work = Path(td)
        baseline_bytes = None
        for label, source, expected in (
            ("baseline", SOURCE, EXPECTED), ("changed", work / "changed.html", MUTATED)
        ):
            if label == "changed":
                source.write_text(original.replace(marker, 'value="6 * 7 + 1"'),
                                  encoding="utf-8")
            iso = work / (label + ".iso")
            build(source, iso, args.cache_dir, args.work_dir)
            code, output = boot(iso, timeout=20)
            if code != SUCCESS_EXIT or output != expected:
                raise AssertionError(
                    f"real QEMU framebuffer {label} failed: exit={code}, output={output!r}; "
                    f"expected {expected!r}")
            if baseline_bytes is None:
                baseline_bytes = iso.read_bytes()
            elif baseline_bytes == iso.read_bytes():
                raise AssertionError("HTML source change did not alter the real framebuffer ISO")
            print(f"M3 QEMU RGB FRAMEBUFFER {label} PIXEL READBACK PASS")
        if EXPECTED == MUTATED:
            raise AssertionError("stale-output negative control not constructed")
    print("M3 REAL NATIVE FRAMEBUFFER QEMU BIOS E2E PASS")


if __name__ == "__main__":
    main()
