#!/usr/bin/env python3
"""Independent exact-integer Python oracle for native division (UBSan O0/O3)."""
from __future__ import annotations

from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def samples(bits: int, signed: bool) -> list[tuple[int, int]]:
    maximum = (1 << (bits - (1 if signed else 0))) - 1
    minimum = -(1 << (bits - 1)) if signed else 0
    values = [minimum, minimum + 1, 0, 1, 2, 5, maximum - 1, maximum]
    divisors = [1, 2, 3, 5, maximum]
    if signed:
        values.extend([-1, -2, -5, -19, -maximum])
        divisors.extend([-1, -2, -3, -5, -maximum])
    pairs: list[tuple[int, int]] = []
    for first, second in ((minimum, -1 if signed else 1),
                          (minimum, 1), (maximum, 1), (maximum, maximum),
                          (0, -1 if signed else 1)):
        pairs.append((first, second))
    rng = random.Random(4831 + bits + (100 if signed else 0))
    for _ in range(59):
        pairs.append((rng.choice(values), rng.choice(divisors)))
    assert len(pairs) == 64 and all(y != 0 for _, y in pairs)
    return pairs


def reference(a: int, b: int, bits: int, signed: bool) -> tuple[int, int]:
    if not signed:
        return a // b, a % b
    minimum = -(1 << (bits - 1))
    if a == minimum and b == -1:
        return minimum, 0  # explicitly specified wrap at signed overflow
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q, a - q * b  # trunc-to-zero remainder, independent of C


def main() -> None:
    statements = ["<print>Native division oracle</print>"]
    expected = ["Native division oracle"]
    for kind in ("u32", "u64", "i32", "i64"):
        bits = int(kind[1:])
        signed = kind.startswith("i")
        for left, right in samples(bits, signed):
            quotient, remainder = reference(left, right, bits, signed)
            for operator, oracle in (("/", quotient), ("%", remainder)):
                statements.append(
                    f'<print value="{kind}({left}) {operator} {kind}({right})"/>'
                )
                expected.append(str(oracle))
    source = '<kernel arch="x86_64"><onboot>' + ''.join(statements) + '</onboot></kernel>'
    oracle = '\n'.join(expected) + '\n'
    (ROOT / "build").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="htmlk-div-oracle-", dir=ROOT / "build") as td:
        work = Path(td)
        html = work / "oracle.html"
        c = work / "oracle.c"
        html.write_text(source, encoding="utf-8")
        compile_html = subprocess.run(
            [sys.executable, str(ROOT / "compiler/htmlk.py"), str(html),
             "--target", "linux", "--out", str(c)],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        if compile_html.returncode:
            raise AssertionError(f"oracle compilation failed: {compile_html.stderr}")
        for optimize in ("-O0", "-O3"):
            exe = work / f"oracle-{optimize[1:]}"
            compiled = subprocess.run(
                ["gcc", "-std=c11", optimize, "-Wall", "-Wextra", "-Werror",
                 "-fsanitize=undefined", "-fno-sanitize-recover=all",
                 str(c), "-o", str(exe)],
                capture_output=True, text=True, timeout=60,
            )
            if compiled.returncode:
                raise AssertionError(f"GCC oracle failed ({optimize}): {compiled.stderr}")
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            if run.returncode != 0 or run.stderr or run.stdout != oracle:
                actual_lines = run.stdout.splitlines()
                wanted_lines = oracle.splitlines()
                mismatch = next((i for i, (a, b) in enumerate(zip(actual_lines, wanted_lines))
                                 if a != b), min(len(actual_lines), len(wanted_lines)))
                raise AssertionError(
                    f"oracle {optimize} mismatch at line {mismatch}, "
                    f"actual={actual_lines[mismatch:mismatch+1]!r}, "
                    f"expected={wanted_lines[mismatch:mismatch+1]!r}, "
                    f"exit={run.returncode}, stderr={run.stderr!r}"
                )
            print(f"DIVISION ORACLE {optimize}: 512 exact signed/unsigned results PASS")
    print("DIVISION INDEPENDENT PYTHON-VS-C UBSAN ORACLE PASS")


if __name__ == "__main__":
    main()
