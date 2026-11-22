#!/usr/bin/env python3
"""Verify real QEMU and Linux if/else behavior, changed source, invalid branches."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

ORIGINAL = ("HTML if/else native!\nelse branch PASS\n"
            "8\n17\n222\nnested PASS\nnested PASS\n")
MUTATED = ("HTML if/else native!\nelse branch PASS\n"
           "9\n17\n222\nnested PASS\nnested PASS\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    ap.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = ap.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    fixture = ROOT / "examples/else-kernel.html"
    original = fixture.read_text(encoding="utf-8")
    old = '<let name="bonus" type="u64" value="3"/>'
    if original.count(old) != 1:
        raise AssertionError("else fixture changed; adjust expected output")
    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-else-") as td:
        work = Path(td)
        previous_iso = None
        for name, source, expected in (
            ("original", fixture, ORIGINAL),
            ("mutated", work / "mutated.html", MUTATED),
        ):
            if name == "mutated":
                source.write_text(original.replace(old,
                    '<let name="bonus" type="u64" value="4"/>'), encoding="utf-8")
            build_and_run(source, work, expected)
            iso = work / f"{name}.iso"
            result = build(source, iso, args.cache_dir, args.work_dir)
            if result.returncode:
                raise AssertionError(f"QEMU image build failed: {result.stdout}")
            assert_boot(iso, expected)
            if previous_iso is None:
                previous_iso = iso.read_bytes()
            else:
                if previous_iso == iso.read_bytes():
                    raise AssertionError("HTML changes did not affect ISO bytes")
                try:
                    assert_boot(iso, ORIGINAL)
                except AssertionError:
                    print("IF/ELSE WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("wrong expected output was accepted")

        invalid_sources = {
            "orphan": original.replace(
                '<halt/>', '<else><print>invalid</print></else><halt/>'),
            "duplicate": original.replace(
                '<else>\n        <print>else branch PASS</print>',
                '<else><print>first</print></else>\n'
                '      <else>\n        <print>else branch PASS</print>'),
            "scope": original.replace(
                '<set name="result" value="value + bonus"/>\n      </else>',
                '<set name="result" value="value + bonus"/>\n      </else>'
                '\n    <set name="result" value="bonus"/>'),
        }
        for name, html in invalid_sources.items():
            src = work / f"bad-{name}.html"
            src.write_text(html, encoding="utf-8")
            for target in ("kernel", "linux"):
                dest = work / f"bad-{name}-{target}.c"
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"), str(src),
                     "--target", target, "--out", str(dest)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 or dest.exists():
                    raise AssertionError(f"{name} was accepted ({target}): {result}")
                if "line " not in result.stderr:
                    raise AssertionError(f"{name} lacked source location ({target})")
        print("IF/ELSE BAD-BRANCH/SCOPE NEGATIVE CONTROLS PASS")
    print("IF/ELSE LINUX + REAL QEMU BOOT PASS")


if __name__ == "__main__":
    main()
