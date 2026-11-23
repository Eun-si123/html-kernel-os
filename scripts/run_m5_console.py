#!/usr/bin/env python3
"""Build and interact with the real M5-B x86-64 ISO via QEMU COM1."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_EXIT = 33  # QEMU isa-debug-exit: (0x10 << 1) | 1


def qemu_command(iso: Path, debug_log: Path) -> list[str]:
    return [
        "qemu-system-x86_64", "-M", "q35", "-m", "256M",
        "-cdrom", str(iso), "-boot", "d", "-display", "none",
        "-serial", "stdio", "-monitor", "none", "-net", "none",
        "-debugcon", "file:" + str(debug_log),
        "-global", "isa-debugcon.iobase=0xe9",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-no-reboot",
    ]


def build_command(iso: Path, romfs_root: Path, *, with_user_program: bool = False) -> list[str]:
    mode = (["--exception-idt", "--tss-ist", "--romfs-run-console"]
            if with_user_program else ["--romfs-console"])
    return [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        *mode, "--romfs-root", str(romfs_root),
        "--out", str(iso), "--test-exit",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-user-program", action="store_true",
                        help="M5-D1: enable real 'run /apps/hello.hke' CPL3 command")
    parser.add_argument("--iso", type=Path, default=None,
                        help="Build output ISO; does not mount a host disk in the guest")
    parser.add_argument("--romfs-root", type=Path, default=ROOT / "examples/romfs",
                        help="Bounded trusted files embedded at compile time")
    parser.add_argument("--debug-log", type=Path,
                        default=ROOT / "build/m5-interactive-debugcon.log")
    parser.add_argument("--reuse-iso", action="store_true",
                        help="Skip rebuild only if the named ISO already exists")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("M5 console needs an interactive TTY; for CI use scripts/test_m5_console.py")
    if shutil.which("qemu-system-x86_64") is None:
        parser.error("qemu-system-x86_64 is required (Ubuntu: qemu-system-x86)")
    iso = (args.iso or ROOT / ("build/m5-interactive-run.iso"
                                if args.with_user_program else "build/m5-interactive.iso")).resolve()
    log = args.debug_log.resolve()
    if iso == log:
        parser.error("ISO and debugcon log cannot be the same file")
    if not args.reuse_iso or not iso.is_file():
        iso.parent.mkdir(parents=True, exist_ok=True)
        print("Building native HTML Kernel OS " +
              ("M5-D1" if args.with_user_program else "M5-B") + " ISO ...", flush=True)
        build = subprocess.run(build_command(iso, args.romfs_root.resolve(),
                                             with_user_program=args.with_user_program),
                               cwd=ROOT, check=False)
        if build.returncode != 0:
            print("M5 console ISO build failed", file=sys.stderr)
            return 1
    log.parent.mkdir(parents=True, exist_ok=True)
    commands = "help, ls, cat /welcome.txt, "
    if args.with_user_program:
        commands += "run /apps/hello.hke, "
    commands += "exit"
    print("Actual QEMU serial console. Commands: " + commands, flush=True)
    print("The guest runs at the virtual COM1 port; no host disk or network is attached.", flush=True)
    guest = subprocess.run(qemu_command(iso, log), cwd=ROOT, check=False)
    if guest.returncode != SUCCESS_EXIT:
        print(f"Guest did not complete normally: QEMU exit {guest.returncode}; log {log}",
              file=sys.stderr)
        return 1
    print(f"Guest completed; QEMU debugcon log: {log}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
