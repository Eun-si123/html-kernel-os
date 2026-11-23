#!/usr/bin/env python3
"""M2 native gate: five representative beginner exercises and negative controls."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

EXPECTED = "M2 tasks\n14\n15\n120\nnegative\n12\nM2 PASS\n"
CHANGED = "M2 tasks\n14\n15\n120\nnegative\n13\nM2 PASS\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    p.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opt = p.parse_args()
    opt.work_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/m2-exercises-kernel.html"
    original = source.read_text(encoding="utf-8")
    original_mark = '<store name="items" index="1" value="12"/>'
    if original.count(original_mark) != 1:
        raise AssertionError("M2 source fixture changed unexpectedly")
    with tempfile.TemporaryDirectory(dir=opt.work_dir, prefix="htmlk-m2-gate-") as td:
        work = Path(td)
        before = None
        for label, html, expected in (
            ("baseline", source, EXPECTED), ("modified", work / "mutated.html", CHANGED)
        ):
            if label == "modified":
                html.write_text(original.replace(
                    original_mark, '<store name="items" index="1" value="13"/>'),
                    encoding="utf-8")
            build_and_run(html, work, expected)
            iso = work / (label + ".iso")
            result = build(html, iso, opt.cache_dir, opt.work_dir)
            if result.returncode:
                raise AssertionError(f"M2 {label} boot image build failure: {result.stdout}")
            assert_boot(iso, expected)
            if before is None:
                before = iso.read_bytes()
            elif before == iso.read_bytes():
                raise AssertionError("M2 mutation did not change the bootable image")
        invalid = work / "bad.html"
        invalid.write_text(original.replace(
            '<store name="items" index="1" value="12"/>',
            '<store name="items" index="4" value="12"/>'
        ), encoding="utf-8")
        invalid_iso = work / "bad.iso"
        result = build(invalid, invalid_iso, opt.cache_dir, opt.work_dir)
        if result.returncode == 0 or invalid_iso.exists() or "out of bounds" not in result.stdout:
            raise AssertionError("M2 negative compile-time safety test was not rejected")
        print("M2 five exercise compiler rejection PASS")
    print("M2 FIVE EXERCISES LINUX AND QEMU BIOS PASS")


if __name__ == "__main__":
    main()
