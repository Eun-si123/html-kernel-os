#!/usr/bin/env python3
"""Execute one HTML Kernel program as an unprivileged Linux x86-64 process."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_M1 = "Hello from HTML Kernel!\nNative code, not a browser.\n"
EXPECTED_M2 = ("Arithmetic in HTML Kernel!\n14\n16\n18\ncondition PASS\n"
               "18446744073709551615\n")
EXPECTED_CHANGED = ("Arithmetic in HTML Kernel!\n13\n15\n17\n"
                    "18446744073709551615\n")


def command(args: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True,
                          check=False, timeout=timeout)


def build_and_run(source: Path, work: Path, expected: str) -> None:
    generated = work / "linux.c"
    binary = work / "htmlk-linux"
    compile_result = command([sys.executable, str(ROOT / "compiler/htmlk.py"),
                              str(source), "--target", "linux", "--out", str(generated)])
    if compile_result.returncode:
        raise AssertionError("compiler error:\n" + compile_result.stderr)
    c_source = generated.read_text()
    if "__asm__" in c_source or "serial_init" in c_source:
        raise AssertionError("Linux target unexpectedly used privileged kernel I/O")

    gcc = command(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                   str(generated), "-o", str(binary)])
    if gcc.returncode:
        raise AssertionError("GCC error:\n" + gcc.stderr)
    result = command([str(binary)], timeout=5)
    if result.returncode or result.stdout != expected or result.stderr:
        raise AssertionError(f"Linux result mismatch: rc={result.returncode} "
                             f"stdout={result.stdout!r} stderr={result.stderr!r}")
    print(f"LINUX PASS: stdout={result.stdout!r} exit=0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path,
                        default=Path(os.environ.get("HTMLK_WORK_DIR", str(ROOT / "build"))))
    a = parser.parse_args()
    a.work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="htmlk-linux-", dir=a.work_dir) as td:
        work = Path(td)
        build_and_run(ROOT / "examples/kernel.html", work, EXPECTED_M1)
        build_and_run(ROOT / "examples/math-kernel.html", work, EXPECTED_M2)
        changed = work / "changed.html"
        original = (ROOT / "examples/math-kernel.html").read_text(encoding="utf-8")
        if 'value="2 + 3 * 4"' not in original:
            raise AssertionError("arithmetic fixture changed")
        changed.write_text(original.replace('value="2 + 3 * 4"',
                                            'value="1 + 3 * 4"'), encoding="utf-8")
        build_and_run(changed, work, EXPECTED_CHANGED)

        invalid = work / "invalid.html"
        invalid.write_text(original.replace('value="2 + 3 * 4"',
                                            'value="__import__(1)"'), encoding="utf-8")
        result = command([sys.executable, str(ROOT / "compiler/htmlk.py"),
                          str(invalid), "--target", "linux",
                          "--out", str(work / "invalid.c")])
        if result.returncode == 0 or (work / "invalid.c").exists():
            raise AssertionError("invalid Linux source was accepted or generated")
        print("LINUX INVALID SOURCE REJECTION PASS")
    print("P2 LINUX USERSPACE PROOF PASS")


if __name__ == "__main__":
    main()
