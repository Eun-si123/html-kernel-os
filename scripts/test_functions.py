#!/usr/bin/env python3
"""M2 function end-to-end proof: native QEMU and Linux from the same HTML."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

ORIGINAL = "Functions in HTML Kernel!\n13\n17\nfunction PASS\n10\n12\n"
MUTATED = "Functions in HTML Kernel!\n15\n19\n10\n12\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/functions-kernel.html"
    original = source.read_text(encoding="utf-8")
    if original.count('<return value="7"/>') != 1:
        raise AssertionError("function fixture changed unexpectedly")

    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-functions-") as tmp:
        directory = Path(tmp)
        for label, file, expected in [
            ("original", source, ORIGINAL),
            ("mutated", directory / "mutated.html", MUTATED),
        ]:
            if label == "mutated":
                file.write_text(original.replace('<return value="7"/>',
                                                 '<return value="9"/>'),
                                encoding="utf-8")
            build_and_run(file, directory, expected)
            image = directory / f"{label}.iso"
            result = build(file, image, args.cache_dir, args.work_dir)
            if result.returncode:
                raise AssertionError(f"QEMU build failed ({label}):\n{result.stdout}")
            assert_boot(image, expected)
            if label == "original":
                original_iso = image.read_bytes()
            else:
                if original_iso == image.read_bytes():
                    raise AssertionError("source edit did not change the bootable image")
                try:
                    assert_boot(image, ORIGINAL)
                except AssertionError:
                    print("FUNCTIONS WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("wrong expected output was accepted")

        invalid = directory / "recursion.html"
        invalid.write_text(
            original.replace('<return value="x * 2"/>',
                             '<return value="double(x)"/>'), encoding="utf-8"
        )
        for target in ("kernel", "linux"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "compiler/htmlk.py"), str(invalid),
                 "--target", target, "--out", str(directory / "invalid.c")],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 or "recursive function calls" not in result.stderr:
                raise AssertionError(f"unsafe recursion not rejected ({target}): {result}")
        print("FUNCTIONS UNSAFE-RECURSION REJECTION PASS")
    print("M2 FUNCTIONS QEMU + LINUX E2E PASS")


if __name__ == "__main__":
    main()
