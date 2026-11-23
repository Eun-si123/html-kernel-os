#!/usr/bin/env python3
"""Real BIOS QEMU and Linux proof for checked native arrays and zero init."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, boot, build
from test_linux import build_and_run

BASE = "Checked array native!\n0\n3\n6\n9\n17\narray PASS\n"
CHANGED = "Checked array native!\n0\n4\n8\n12\n17\narray PASS\n"
FAULT_STDOUT = "Checked array native!\n0\n3\n6\n"
FAULT_MSG = "HTMLK_ARRAY_BOUNDS\n"


def linux_build(source: Path, work: Path) -> Path:
    generated = work / "array.c"
    binary = work / "array-linux"
    result = subprocess.run(
        [sys.executable, str(ROOT / "compiler/htmlk.py"), str(source),
         "--target", "linux", "--out", str(generated)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    if result.returncode:
        raise AssertionError(f"array compiler failure: {result.stderr}")
    result = subprocess.run(
        ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
         "-fsanitize=undefined", "-fno-sanitize-recover=all",
         str(generated), "-o", str(binary)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise AssertionError(f"array gcc failure: {result.stderr}")
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    original = ROOT / "examples/array-kernel.html"
    source_text = original.read_text(encoding="utf-8")
    if source_text.count('value="i * 3"') != 1:
        raise AssertionError("array fixture source unexpectedly changed")
    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-array-") as td:
        work = Path(td)
        baseline_iso = None
        for label, html, expected in (
            ("original", original, BASE), ("modified", work / "modified.html", CHANGED),
        ):
            if label == "modified":
                html.write_text(source_text.replace('value="i * 3"', 'value="i * 4"'),
                                encoding="utf-8")
            build_and_run(html, work, expected)
            iso = work / f"{label}.iso"
            result = build(html, iso, args.cache_dir, args.work_dir)
            if result.returncode:
                raise AssertionError(f"QEMU build failed: {result.stdout}")
            assert_boot(iso, expected)
            if baseline_iso is None:
                baseline_iso = iso.read_bytes()
            elif baseline_iso == iso.read_bytes():
                raise AssertionError("array mutation failed to change native ISO")

        invalid = work / "invalid.html"
        invalid.write_text(source_text.replace(
            '<print value="items[3]"/>',
            '<let name="outside" type="u64" value="4"/>'
            '<print value="items[outside]"/>'
        ), encoding="utf-8")
        binary = linux_build(invalid, work)
        run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if run.returncode != 66 or run.stdout != FAULT_STDOUT or run.stderr != FAULT_MSG:
            raise AssertionError(f"Linux index bounds failure: {run.returncode} "
                                 f"{run.stdout!r} {run.stderr!r}")
        iso = work / "bounds.iso"
        result = build(invalid, iso, args.cache_dir, args.work_dir)
        if result.returncode:
            raise AssertionError(f"QEMU bounds build failed: {result.stdout}")
        code, stdout = boot(iso)
        if code != 37 or stdout != FAULT_STDOUT + FAULT_MSG:
            raise AssertionError(f"QEMU bounds did not trap with non-success exit: "
                                 f"{code}, {stdout!r}")
        print("ARRAY RUNTIME OOB LINUX+QEMU TRAP PASS")
        compile_bad = work / "out-of-bounds-literal.html"
        compile_bad.write_text(source_text.replace(
            '<print value="items[3]"/>', '<print value="items[4]"/>'),
            encoding="utf-8")
        out = work / "should-not-build.c"
        for target in ("kernel", "linux"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "compiler/htmlk.py"),
                 str(compile_bad), "--target", target, "--out", str(out)],
                cwd=ROOT, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 or out.exists() or "out of bounds" not in result.stderr:
                raise AssertionError(f"{target} accepted literal out-of-bounds index")
        print("ARRAY COMPILE-TIME OOB NEGATIVE CONTROL PASS")
    print("M2 CHECKED ARRAYS LINUX AND QEMU E2E PASS")


if __name__ == "__main__":
    main()
