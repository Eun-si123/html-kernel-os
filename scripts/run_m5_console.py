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


def qemu_command(iso: Path, debug_log: Path, *, user_timeout: bool = False) -> list[str]:
    return [
        "qemu-system-x86_64", "-M", "q35", "-m", "256M",
        *(["-cpu", "qemu64,+x2apic", "-smp", "1"] if user_timeout else []),
        "-cdrom", str(iso), "-boot", "d", "-display", "none",
        "-serial", "stdio", "-monitor", "none", "-net", "none",
        "-debugcon", "file:" + str(debug_log),
        "-global", "isa-debugcon.iobase=0xe9",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-no-reboot",
    ]


def build_command(iso: Path, romfs_root: Path, *, with_user_program: bool = False,
                  recover_user_faults: bool = False,
                  user_timeout: bool = False,
                  html_user_app: Path | None = None) -> list[str]:
    if html_user_app is not None and not (
        with_user_program and recover_user_faults and user_timeout):
        raise ValueError("M5-F1 user HTML requires guarded Ring3 and x2APIC timer mode")
    if user_timeout and not recover_user_faults:
        raise ValueError("M5-E2 timer needs M5-E1 fault recovery")
    if recover_user_faults and not with_user_program:
        raise ValueError("M5-E1 needs the interactive Ring3 loader")
    mode = (["--exception-idt", "--tss-ist", "--romfs-run-console"]
            if with_user_program else ["--romfs-console"])
    return [
        sys.executable, str(ROOT / "scripts/build_boot.py"),
        *mode, *(["--user-fault-recover"] if recover_user_faults else []),
        *(["--user-timeout"] if user_timeout else []),
        *(["--user-app-html", str(html_user_app)] if html_user_app else []),
        "--romfs-root", str(romfs_root),
        "--out", str(iso), "--test-exit",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-user-program", action="store_true",
                        help="M5-D1: enable real 'run /apps/hello.hke' CPL3 command")
    parser.add_argument("--recover-user-faults", action="store_true",
                        help="M5-E1: return to shell after guarded CPL3 #GP/#PF/#UD")
    parser.add_argument("--user-timeout", action="store_true",
                        help="M5-E2: stop non-yielding Ring3 user code using real x2APIC IRQ")
    parser.add_argument("--html-user-app", type=Path,
                        help="M5-F1: compile this HTML source as a native Ring3 user app (enables safe M5-E2 shell)")
    parser.add_argument("--iso", type=Path, default=None,
                        help="Build output ISO; does not mount a host disk in the guest")
    parser.add_argument("--romfs-root", type=Path, default=ROOT / "examples/romfs",
                        help="Bounded trusted files embedded at compile time")
    parser.add_argument("--debug-log", type=Path,
                        default=ROOT / "build/m5-interactive-debugcon.log")
    parser.add_argument("--reuse-iso", action="store_true",
                        help="Skip rebuild only if the named ISO already exists")
    args = parser.parse_args(argv)
    if args.html_user_app is not None:
        args.with_user_program = True
        args.recover_user_faults = True
        args.user_timeout = True
        if not args.html_user_app.is_file() or args.html_user_app.is_symlink():
            parser.error("--html-user-app must be an existing regular HTML source file")
    if args.recover_user_faults and not args.with_user_program:
        parser.error("--recover-user-faults requires --with-user-program")
    if args.user_timeout and not args.recover_user_faults:
        parser.error("--user-timeout requires --recover-user-faults and --with-user-program")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("M5 console needs an interactive TTY; for CI use scripts/test_m5_console.py")
    if shutil.which("qemu-system-x86_64") is None:
        parser.error("qemu-system-x86_64 is required (Ubuntu: qemu-system-x86)")
    default_iso = ("build/m5-interactive-html-user.iso" if args.html_user_app else
                   "build/m5-interactive-timeout.iso" if args.user_timeout else
                   "build/m5-interactive-recover.iso" if args.recover_user_faults
                   else "build/m5-interactive-run.iso" if args.with_user_program
                   else "build/m5-interactive.iso")
    iso = (args.iso or ROOT / default_iso).resolve()
    log = args.debug_log.resolve()
    if iso == log:
        parser.error("ISO and debugcon log cannot be the same file")
    if not args.reuse_iso or not iso.is_file():
        iso.parent.mkdir(parents=True, exist_ok=True)
        print("Building native HTML Kernel OS " +
              ("M5-F1" if args.html_user_app else
               "M5-E2" if args.user_timeout else
               "M5-E1" if args.recover_user_faults else
               "M5-D1" if args.with_user_program else "M5-B") + " ISO ...", flush=True)
        build = subprocess.run(build_command(iso, args.romfs_root.resolve(),
                                             with_user_program=args.with_user_program,
                                             recover_user_faults=args.recover_user_faults,
                                             user_timeout=args.user_timeout,
                                             html_user_app=args.html_user_app.resolve()
                                             if args.html_user_app else None),
                               cwd=ROOT, check=False)
        if build.returncode != 0:
            print("M5 console ISO build failed", file=sys.stderr)
            return 1
    log.parent.mkdir(parents=True, exist_ok=True)
    commands = "help, ls, cat /welcome.txt, "
    if args.with_user_program:
        commands += "run /apps/hello.hke, "
    if args.user_timeout:
        commands += "run /apps/spin.hke, "
    if args.recover_user_faults:
        commands += "run /apps/fault-io.hke, run /apps/fault-pf.hke, "
        commands += "run /apps/fault-ro.hke, run /apps/fault-ud.hke, "
    commands += "exit"
    print("Actual QEMU serial console. Commands: " + commands, flush=True)
    print("The guest runs at the virtual COM1 port; no host disk or network is attached.", flush=True)
    guest = subprocess.run(qemu_command(iso, log, user_timeout=args.user_timeout),
                           cwd=ROOT, check=False)
    if guest.returncode != SUCCESS_EXIT:
        print(f"Guest did not complete normally: QEMU exit {guest.returncode}; log {log}",
              file=sys.stderr)
        return 1
    print(f"Guest completed; QEMU debugcon log: {log}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
