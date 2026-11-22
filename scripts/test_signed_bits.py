#!/usr/bin/env python3
"""M2 signed, bitwise and bounded loop control: real QEMU + Linux proofs."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

BASE = (
    "Typed signed integers and bitwise kernel!\n"
    "-2147483648\n2147483647\n1\n2\n"
    "-9223372036854775808\n9223372036854775807\n"
    "-1\n18446744073709551615\n43\n0\n4294967295\n"
    "1\n3\ntyped signed and loop PASS\n"
)
CHANGED = (
    "Typed signed integers and bitwise kernel!\n"
    "-2147483647\n-2147483648\n1\n2\n"
    "-9223372036854775808\n9223372036854775807\n"
    "-1\n18446744073709551615\n43\n0\n4294967295\n"
    "1\n3\ntyped signed and loop FAIL\n"
)


def sanitizer_check(source: Path, work: Path, expected: str) -> None:
    """Cross-optimization UBsan checks catch signed arithmetic mistakes."""
    generated = work / "signed-ubsan.c"
    result = subprocess.run(
        [sys.executable, str(ROOT / "compiler/htmlk.py"), str(source),
         "--target", "linux", "--out", str(generated)],
        cwd=ROOT, text=True, capture_output=True, timeout=10,
    )
    if result.returncode:
        raise AssertionError(f"compiler rejected valid code: {result.stderr}")
    for optimize in ("-O0", "-O3"):
        binary = work / ("signed-ubsan-" + optimize[1:])
        compile_result = subprocess.run(
            ["gcc", "-std=c11", optimize, "-Wall", "-Wextra", "-Werror",
             "-fsanitize=undefined", "-fno-sanitize-recover=all",
             str(generated), "-o", str(binary)],
            capture_output=True, text=True, timeout=30,
        )
        if compile_result.returncode:
            raise AssertionError(f"UBsan GCC failed: {compile_result.stderr}")
        run = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=10,
        )
        if run.returncode != 0 or run.stdout != expected or run.stderr:
            raise AssertionError(f"UBsan {optimize}: output={run.stdout!r}, "
                                 f"stderr={run.stderr!r}, exit={run.returncode}")
        print(f"SIGNED UBSAN {optimize} PASS")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    ap.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = ap.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    fixture = ROOT / "examples/signed-bits-kernel.html"
    original = fixture.read_text(encoding="utf-8")
    minimum = '<let name="minimum" type="i32" value="-2147483648"/>'
    condition = 'bitops(5) == 43'
    if original.count(minimum) != 1 or original.count(condition) != 1:
        raise AssertionError("fixture changed; update expected observations")

    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-signed-") as td:
        work = Path(td)
        baseline_iso = None
        for label, source, expected in (
            ("baseline", fixture, BASE),
            ("changed", work / "changed.html", CHANGED),
        ):
            if label == "changed":
                source.write_text(
                    original.replace(minimum,
                        '<let name="minimum" type="i32" value="-2147483647"/>'
                    ).replace(condition, "bitops(5) == 42"),
                    encoding="utf-8",
                )
            build_and_run(source, work, expected)
            sanitizer_check(source, work, expected)
            iso = work / (label + ".iso")
            built = build(source, iso, args.cache_dir, args.work_dir)
            if built.returncode:
                raise AssertionError(f"QEMU image failed to build ({label}): {built.stdout}")
            assert_boot(iso, expected)
            if baseline_iso is None:
                baseline_iso = iso.read_bytes()
            else:
                if baseline_iso == iso.read_bytes():
                    raise AssertionError("HTML source mutation did not alter boot image")
                try:
                    assert_boot(iso, BASE)
                except AssertionError:
                    print("SIGNED/BITWISE WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("changed ISO accepted stale expected output")

        invalid = {
            "range": original.replace(minimum,
                '<let name="minimum" type="i32" value="-2147483649"/>'),
            "mixed-width": original.replace(
                '<print value="minimum"/>',
                '<print value="minimum + u32(1)"/>'),
            "signed-bitwise": original.replace(
                '<print value="bitops(5)"/>',
                '<print value="minimum &amp; 3"/>'),
            "orphan-break": original.replace(
                '<halt/>', '<break/><halt/>'),
            "no-cast": original.replace(
                '<print value="u64(i64(-1))"/>',
                '<print value="u64(1) + i64(-1)"/>'),
        }
        for label, html in invalid.items():
            src = work / f"invalid-{label}.html"
            src.write_text(html, encoding="utf-8")
            for target in ("linux", "kernel"):
                output = work / f"invalid-{label}-{target}.c"
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"),
                     str(src), "--target", target, "--out", str(output)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 or output.exists():
                    raise AssertionError(f"{label} was accepted by {target}: {result}")
                if str(src) not in result.stderr or "line " not in result.stderr:
                    raise AssertionError(f"{label} lacked error location: {result.stderr}")
        print("SIGNED/SHIFT/CONTROL INVALID-SOURCE REJECTION PASS")
    print("SIGNED + BITWISE + LOOP CONTROL NATIVE LINUX/QEMU E2E PASS")


if __name__ == "__main__":
    main()
