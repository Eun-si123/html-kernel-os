#!/usr/bin/env python3
"""M2 integration proof: expressions, variables, loops and branches boot for real."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

from test_boot import assert_boot, build, ROOT

ORIGINAL_OUTPUT = (
    "Arithmetic in HTML Kernel!\n14\n16\n18\ncondition PASS\n"
    "18446744073709551615\n"
)
MUTATED_OUTPUT = (
    "Arithmetic in HTML Kernel!\n13\n15\n17\n"
    "18446744073709551615\n"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-m2-") as td:
        tmp = Path(td)
        original = ROOT / "examples/math-kernel.html"
        first_iso = tmp / "arithmetic.iso"
        result = build(original, first_iso, args.cache_dir, args.work_dir)
        if result.returncode:
            raise AssertionError("M2 build failed:\n" + result.stdout)
        assert_boot(first_iso, ORIGINAL_OUTPUT)

        changed_source = tmp / "changed.html"
        initial = original.read_text(encoding="utf-8")
        if 'value="2 + 3 * 4"' not in initial:
            raise AssertionError("M2 source fixture unexpectedly changed")
        changed_source.write_text(initial.replace(
            'value="2 + 3 * 4"', 'value="1 + 3 * 4"'), encoding="utf-8")
        second_iso = tmp / "changed.iso"
        result = build(changed_source, second_iso, args.cache_dir, args.work_dir)
        if result.returncode:
            raise AssertionError("M2 changed-source build failed:\n" + result.stdout)
        assert_boot(second_iso, MUTATED_OUTPUT)
        if first_iso.read_bytes() == second_iso.read_bytes():
            raise AssertionError("M2 source changes did not affect the boot ISO")
        try:
            assert_boot(second_iso, ORIGINAL_OUTPUT)
        except AssertionError:
            print("M2 WRONG-OUTPUT NEGATIVE CONTROL PASS", flush=True)
        else:
            raise AssertionError("M2 negative check failed to detect wrong output")

        bad = tmp / "bad.html"
        bad.write_text(initial.replace('value="2 + 3 * 4"',
                                       'value="__import__(1)"'), encoding="utf-8")
        result = build(bad, tmp / "bad.iso", args.cache_dir, args.work_dir)
        if result.returncode == 0:
            raise AssertionError("unsafe expression unexpectedly built")
        print("M2 INVALID-EXPRESSION REJECTION PASS", flush=True)
    print("M2 REAL QEMU INTEGRATION PASS", flush=True)


if __name__ == "__main__":
    main()
