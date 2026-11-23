#!/usr/bin/env python3
"""Execute signed/unsigned division in Linux+QEMU, including real zero faults."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, boot, build
from test_linux import build_and_run


BASE = (
    "Native division in HTML Kernel!\n"
    "-3\n-2\n-2147483648\n0\n2147483647\n1\n"
    "6148914691236517205\n0\n-4\ndivision PASS\n"
)
MUTATED = (
    "Native division in HTML Kernel!\n"
    "-3\n-3\n-2147483648\n0\n2147483647\n1\n"
    "6148914691236517205\n0\n-4\n"
)
FAULT = "HTMLK_DIVIDE_BY_ZERO\n"
BANNER = "Native division in HTML Kernel!\n"


def compile_linux(source: Path, work: Path, optimize: str,
                  sanitizer: bool = False) -> Path:
    c_file = work / "division.c"
    generated = subprocess.run(
        [sys.executable, str(ROOT / "compiler/htmlk.py"), str(source),
         "--target", "linux", "--out", str(c_file)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    if generated.returncode:
        raise AssertionError(f"compiler rejected valid source: {generated.stderr}")
    binary = work / ("division-" + optimize.removeprefix("-") +
                     ("-ubsan" if sanitizer else ""))
    options = ["-fsanitize=undefined", "-fno-sanitize-recover=all"] if sanitizer else []
    compiled = subprocess.run(
        ["gcc", "-std=c11", optimize, "-Wall", "-Wextra", "-Werror",
         *options, str(c_file), "-o", str(binary)],
        capture_output=True, text=True, timeout=30,
    )
    if compiled.returncode:
        raise AssertionError(f"GCC rejected division helper: {compiled.stderr}")
    return binary


def sanitizer_check(source: Path, work: Path, expected: str) -> None:
    for opt in ("-O0", "-O3"):
        binary = compile_linux(source, work, opt, sanitizer=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or result.stdout != expected or result.stderr:
            raise AssertionError(
                f"division UBSan {opt} failed: {result.returncode}, "
                f"{result.stdout!r}, {result.stderr!r}"
            )
        print(f"DIVISION UBSAN {opt} PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opts = parser.parse_args()
    opts.work_dir.mkdir(parents=True, exist_ok=True)
    original = ROOT / "examples/division-kernel.html"
    data = original.read_text(encoding="utf-8")
    before = '<let name="a" type="i32" value="-17"/>'
    if data.count(before) != 1 or data.count('<print value="a / 5"/>') != 1:
        raise AssertionError("division fixture unexpectedly changed")
    with tempfile.TemporaryDirectory(dir=opts.work_dir, prefix="htmlk-div-") as tmp:
        work = Path(tmp)
        reference_iso = None
        for label, source, expected in (
            ("baseline", original, BASE),
            ("mutated", work / "mutated.html", MUTATED),
        ):
            if label == "mutated":
                source.write_text(data.replace(
                    before, '<let name="a" type="i32" value="-18"/>'),
                    encoding="utf-8",
                )
            build_and_run(source, work, expected)
            sanitizer_check(source, work, expected)
            iso = work / f"{label}.iso"
            built = build(source, iso, opts.cache_dir, opts.work_dir)
            if built.returncode:
                raise AssertionError(f"QEMU kernel build failed ({label}): {built.stdout}")
            assert_boot(iso, expected)
            if reference_iso is None:
                reference_iso = iso.read_bytes()
            else:
                if reference_iso == iso.read_bytes():
                    raise AssertionError("source mutation did not change ISO")
                try:
                    assert_boot(iso, BASE)
                except AssertionError:
                    print("DIVISION WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("stale expected stdout was wrongly accepted")

        fault = work / "fault.html"
        fault.write_text(data.replace(
            '<print value="a / 5"/>',
            '<let name="zero" type="i32" value="0"/><print value="a / zero"/>'
        ), encoding="utf-8")
        binary = compile_linux(fault, work, "-O2")
        run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if (run.returncode != 65 or run.stdout != BANNER or
                run.stderr != FAULT):
            raise AssertionError(
                f"Linux divide-zero fault not deterministic: "
                f"{run.returncode}, {run.stdout!r}, {run.stderr!r}"
            )
        iso = work / "fault.iso"
        built = build(fault, iso, opts.cache_dir, opts.work_dir)
        if built.returncode:
            raise AssertionError(f"QEMU fault kernel build failed: {built.stdout}")
        code, debugcon = boot(iso)
        # isa-debug-exit return is (0x11 << 1) | 1 = 35.
        if code != 35 or debugcon != BANNER + FAULT:
            raise AssertionError(
                f"QEMU divide-zero was not a distinct fault: {code}, {debugcon!r}")
        print("DIVISION REAL LINUX AND QEMU ZERO-FAULT TEST PASS")

        invalid = {
            "literal-zero": data.replace(
                '<print value="a / 5"/>', '<print value="a / 0"/>'),
            "literal-zero-mod": data.replace(
                '<print value="a % 5"/>', '<print value="a % 0"/>'),
            "mixed-type": data.replace(
                '<print value="a / 5"/>', '<print value="a / u32(5)"/>'),
        }
        for name, html in invalid.items():
            source = work / f"invalid-{name}.html"
            source.write_text(html, encoding="utf-8")
            for target in ("linux", "kernel"):
                dest = work / f"invalid-{name}-{target}.c"
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"),
                     str(source), "--target", target, "--out", str(dest)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 or dest.exists():
                    raise AssertionError(f"{name} accepted by {target}")
                if str(source) not in result.stderr or "line " not in result.stderr:
                    raise AssertionError(f"{name} missing source location: {result.stderr}")
        print("DIVISION INVALID SOURCE REJECTION PASS")
    print("M2 SAFE INTEGER DIVISION/MODULO NATIVE E2E PASS")


if __name__ == "__main__":
    main()
