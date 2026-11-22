#!/usr/bin/env python3
"""End-to-end native kernel proof: source changes affect actual QEMU boot."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_EXIT = 33  # isa-debug-exit device: (0x10 << 1) | 1


def boot(iso: Path, *, timeout: int = 12) -> tuple[int, str]:
    args = [
        "qemu-system-x86_64", "-M", "q35", "-m", "256M",
        "-cdrom", str(iso), "-boot", "d",
        "-display", "none", "-serial", "none", "-monitor", "none",
        "-net", "none", "-debugcon", "stdio",
        "-global", "isa-debugcon.iobase=0xe9",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-no-reboot",
    ]
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"QEMU boot timed out after {timeout}s") from exc
    return result.returncode, result.stdout.decode("utf-8", errors="replace")


def assert_boot(iso: Path, expected: str) -> None:
    code, output = boot(iso)
    if code != SUCCESS_EXIT:
        raise AssertionError(f"QEMU returned {code}, not {SUCCESS_EXIT}; output={output!r}")
    if output != expected:
        raise AssertionError(f"QEMU output mismatch: {output!r} != {expected!r}")
    print(f"QEMU BIOS BOOT PASS: exit={code}, output={output!r}", flush=True)


def build(src: Path, out: Path, cache: Path, work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        "--source", str(src), "--out", str(out),
        "--cache-dir", str(cache), "--work-dir", str(work),
        "--test-exit",
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-dir", type=Path, default=Path(os.environ.get(
        "HTMLK_CACHE_DIR", str(ROOT / "build/.cache"))))
    p.add_argument("--work-dir", type=Path, default=Path(os.environ.get(
        "HTMLK_WORK_DIR", str(ROOT / "build"))))
    args = p.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="htmlk-e2e-", dir=args.work_dir) as td:
        root = Path(td)
        baseline = ROOT / "examples/kernel.html"
        original = baseline.read_text(encoding="utf-8")
        assert "Hello from HTML Kernel!" in original
        first = root / "first.iso"
        output = build(baseline, first, args.cache_dir, args.work_dir)
        if output.returncode:
            raise AssertionError(f"Initial build failed:\n{output.stdout}")
        assert_boot(first, "Hello from HTML Kernel!\nNative code, not a browser.\n")

        changed = root / "changed.html"
        changed.write_text(original.replace(
            "Hello from HTML Kernel!", "Changed HTML source is really executing!"
        ), encoding="utf-8")
        second = root / "second.iso"
        result = build(changed, second, args.cache_dir, args.work_dir)
        if result.returncode:
            raise AssertionError(f"Altered source build failed:\n{result.stdout}")
        assert_boot(second, "Changed HTML source is really executing!\nNative code, not a browser.\n")
        if first.read_bytes() == second.read_bytes():
            raise AssertionError("HTML edits did not change the boot image")
        print("SOURCE PROVENANCE PASS: altered HTML changed the actual ISO and QEMU output")
        # Negative oracle: expected output cannot be faked by a bootloader banner.
        try:
            assert_boot(second, "Hello from HTML Kernel!\nNative code, not a browser.\n")
        except AssertionError as exc:
            print("WRONG-OUTPUT REJECTION PASS:", exc)
        else:
            raise AssertionError("negative wrong-output check incorrectly passed")

        invalid = root / "invalid.html"
        invalid.write_text("<kernel><onboot><unknown/></onboot></kernel>", encoding="utf-8")
        result = build(invalid, root / "invalid.iso", args.cache_dir, args.work_dir)
        if result.returncode == 0:
            raise AssertionError("invalid source unexpectedly built")
        print("INVALID-SOURCE REJECTION PASS")
        print("M1 QEMU BOOT PROVEN WITH NEGATIVE CONTROLS")


if __name__ == "__main__":
    main()
