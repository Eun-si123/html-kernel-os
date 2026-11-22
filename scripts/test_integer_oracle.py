#!/usr/bin/env python3
"""Independent deterministic Python arithmetic oracle for generated C.

Exercise signed wrap, explicit casting, unsigned bitwise and overshifts at
two optimization levels with UBSan. No runtime eval/exec of HTML expressions.
"""
from __future__ import annotations

from pathlib import Path
import random
import subprocess
import sys
import tempfile

from test_boot import ROOT


def as_signed(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def build_source() -> tuple[str, str, int]:
    rng = random.Random(0x48_54_4D_4C_4B)
    statements: list[str] = []
    results: list[str] = []
    for bits in (32, 64):
        limit = (1 << bits) - 1
        boundaries = [0, 1, 2, (1 << (bits - 1)) - 1,
                      1 << (bits - 1), limit - 1, limit]
        values = [(boundaries[i % len(boundaries)], boundaries[(i + 2) % len(boundaries)])
                  for i in range(len(boundaries))]
        values.extend((rng.getrandbits(bits), rng.getrandbits(bits)) for _ in range(22))
        convert = f"i{bits}(u{bits}({{}}))"
        for a, b in values:
            arg_a = convert.format(a)
            arg_b = convert.format(b)
            expected_a, expected_b = as_signed(a, bits), as_signed(b, bits)
            for source, value in [
                (f"{arg_a} + {arg_b}", expected_a + expected_b),
                (f"{arg_a} - {arg_b}", expected_a - expected_b),
                (f"{arg_a} * {arg_b}", expected_a * expected_b),
                (f"-{arg_a}", -expected_a),
            ]:
                statements.append(f'<print value="{source}"/>')
                results.append(str(as_signed(value, bits)))
            shift = rng.choice([0, 1, bits - 1, bits, bits + 1, 100])
            for source, value in [
                (f"u{bits}({a}) &amp; u{bits}({b})", a & b),
                (f"u{bits}({a}) ^ u{bits}({b})", a ^ b),
                (f"u{bits}({a}) &lt;&lt; {shift}",
                 (a << shift) & limit if shift < bits else 0),
                (f"u{bits}({a}) &gt;&gt; {shift}",
                 (a >> shift) if shift < bits else 0),
            ]:
                statements.append(f'<print value="{source}"/>')
                results.append(str(value))
    source = ('<kernel arch="x86_64"><onboot><print>integer oracle</print>'
              + "".join(statements) + '<halt/></onboot></kernel>')
    return source, "integer oracle\n" + "\n".join(results) + "\n", len(statements)


def main() -> None:
    html, expected, count = build_source()
    if count < 400 or len(expected) >= 12_000:
        raise AssertionError("unexpected test-oracle bounds")
    with tempfile.TemporaryDirectory(prefix="htmlk-int-oracle-") as td:
        folder = Path(td)
        source = folder / "oracle.html"
        generated = folder / "oracle.c"
        source.write_text(html, encoding="utf-8")
        compiler = subprocess.run(
            [sys.executable, str(ROOT / "compiler/htmlk.py"), str(source),
             "--target", "linux", "--out", str(generated)],
            capture_output=True, text=True, timeout=10,
        )
        if compiler.returncode:
            raise AssertionError(f"source not accepted: {compiler.stderr}")
        for optimize in ("-O0", "-O3"):
            binary = folder / ("oracle-" + optimize[1:])
            cc = subprocess.run(
                ["gcc", "-std=c11", optimize, "-Wall", "-Wextra", "-Werror",
                 "-fsanitize=undefined", "-fno-sanitize-recover=all",
                 str(generated), "-o", str(binary)],
                capture_output=True, text=True, timeout=30,
            )
            if cc.returncode:
                raise AssertionError(f"GCC+UBSan {optimize}: {cc.stderr}")
            actual = subprocess.run(
                [str(binary)], capture_output=True, text=True, timeout=10,
            )
            if actual.returncode != 0 or actual.stdout != expected or actual.stderr:
                for idx, (a, b) in enumerate(zip(actual.stdout.splitlines(),
                                                  expected.splitlines())):
                    if a != b:
                        raise AssertionError(
                            f"arithmetic differential sample {idx}: actual={a!r}, "
                            f"expected={b!r}, exit={actual.returncode}, "
                            f"stderr={actual.stderr!r}")
                raise AssertionError(f"oracle result length/exit mismatch: "
                                     f"{len(actual.stdout)}, {len(expected)}, {actual.returncode}, {actual.stderr!r}")
            print(f"INTEGER ORACLE {count} CASES UBSAN {optimize} PASS")
    print("INTEGER SIGNED/UNSIGNED DIFFERENTIAL TEST PASS")


if __name__ == "__main__":
    main()
