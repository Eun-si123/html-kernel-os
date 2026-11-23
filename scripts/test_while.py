#!/usr/bin/env python3
"""Verify bounded while against real Linux native code and QEMU BIOS boot."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

BASE = "Bounded while in HTML Kernel!\n0\n1\n2\n3\n5\n2\nwhile PASS\n"
MUTATED = "Bounded while in HTML Kernel!\n0\n1\n2\n5\n2\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / "examples/while-kernel.html"
    original = fixture.read_text(encoding="utf-8")
    needle = '<while test="n &lt; 3" max="5">'
    if original.count(needle) != 1:
        raise AssertionError("bounded while fixture changed; revalidate expected output")

    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-while-") as td:
        work = Path(td)
        baseline = None
        for name, source, expected in (
            ("original", fixture, BASE),
            ("mutated", work / "changed.html", MUTATED),
        ):
            if name == "mutated":
                source.write_text(
                    original.replace(needle, '<while test="n &lt; 3" max="2">'),
                    encoding="utf-8",
                )
            build_and_run(source, work, expected)
            iso = work / f"{name}.iso"
            result = build(source, iso, args.cache_dir, args.work_dir)
            if result.returncode:
                raise AssertionError(f"QEMU build rejected {name}: {result.stdout}")
            assert_boot(iso, expected)
            if baseline is None:
                baseline = iso.read_bytes()
            else:
                if baseline == iso.read_bytes():
                    raise AssertionError("while source mutation did not alter the image")
                try:
                    assert_boot(iso, BASE)
                except AssertionError:
                    print("BOUNDED WHILE WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("mutated kernel unexpectedly passed stale output")

        bad = {
            "limit": original.replace(needle, '<while test="n &lt; 3" max="65">'),
            "missing-test": original.replace(needle, '<while max="5">'),
            "non-boolean": original.replace(needle, '<while test="n" max="5">'),
            "unbounded": original.replace(needle, '<while test="n &lt; 3">'),
        }
        for name, source in bad.items():
            path = work / f"bad-{name}.html"
            path.write_text(source, encoding="utf-8")
            for target in ("kernel", "linux"):
                c = work / f"bad-{name}-{target}.c"
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"), str(path),
                     "--target", target, "--out", str(c)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 or c.exists():
                    raise AssertionError(f"invalid while {name} accepted ({target}): {result}")
                if str(path) not in result.stderr or "line " not in result.stderr:
                    raise AssertionError(f"missing source diagnostic ({name}): {result.stderr}")
        print("BOUNDED WHILE INVALID SOURCE REJECTION PASS")
    print("M2 BOUNDED WHILE NATIVE LINUX + QEMU E2E PASS")


if __name__ == "__main__":
    main()
