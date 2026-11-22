#!/usr/bin/env python3
"""Compile and run u32/u64 typed HTML in Linux and actual QEMU BIOS."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

ORIGINAL = ("Native u32 types in HTML Kernel!\n"
            "4294967295\n0\n1\n4294967295\n4294967296\ntyped PASS\n")
MUTATED = ("Native u32 types in HTML Kernel!\n"
           "4294967294\n4294967295\n0\n4294967295\n4294967295\ntyped FAIL\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    ap.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = ap.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / "examples/u32-kernel.html"
    original = fixture.read_text(encoding="utf-8")
    needle = '<let name="max" type="u32" value="4294967295"/>'
    if original.count(needle) != 1:
        raise AssertionError("u32 fixture changed unexpectedly")

    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-u32-") as td:
        work = Path(td)
        before = None
        for label, source, expected in (
            ("original", fixture, ORIGINAL),
            ("mutated", work / "mutated.html", MUTATED),
        ):
            if label == "mutated":
                source.write_text(original.replace(
                    needle, '<let name="max" type="u32" value="4294967294"/>'),
                    encoding="utf-8",
                )
            build_and_run(source, work, expected)
            iso = work / f"{label}.iso"
            built = build(source, iso, args.cache_dir, args.work_dir)
            if built.returncode:
                raise AssertionError(f"native QEMU image build failed ({label}): {built.stdout}")
            assert_boot(iso, expected)
            if before is None:
                before = iso.read_bytes()
            else:
                if before == iso.read_bytes():
                    raise AssertionError("u32 source mutation did not change ISO")
                try:
                    assert_boot(iso, ORIGINAL)
                except AssertionError:
                    print("U32 WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("mutated ISO wrongly accepted old output")

        invalid_sources = {
            "overflow": original.replace(
                needle, '<let name="max" type="u32" value="4294967296"/>'),
            "mixing": original.replace(
                '<print value="u32(wide - 1)"/>',
                '<print value="max + wide"/>'),
            "implicit": original.replace(
                '<print value="sum64(u64(max))"/>',
                '<print value="sum64(max)"/>'),
        }
        for name, html in invalid_sources.items():
            src = work / (name + ".html")
            src.write_text(html, encoding="utf-8")
            for target in ("kernel", "linux"):
                output = work / (name + "-" + target + ".c")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"),
                     str(src), "--target", target, "--out", str(output)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 or output.exists():
                    raise AssertionError(f"{name} accepted on {target}: {result}")
                if str(src) not in result.stderr or "line " not in result.stderr:
                    raise AssertionError(f"{name} error missing file or line: {result.stderr}")
        print("U32 RANGE/TYPE/IMPLICIT-CONVERSION REJECTION PASS")
    print("M2 U32 NATIVE LINUX + REAL QEMU BOOT PASS")


if __name__ == "__main__":
    main()
