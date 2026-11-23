#!/usr/bin/env python3
"""M5-D1 actual UART command -> ROMFS HKEX -> CPL3 -> prompt -> exit."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_boot import ROOT, SUCCESS_EXIT

BASE = b"M3_TSS_IST_READY\nM3_IDT_READY\nM5_CONSOLE_READY\nM5_PROMPT> "
HTML = b"Hello from HTML Kernel!\nNative code, not a browser.\n"
APP_TRACE = (b"M5_RUN_START /apps/hello.hke\n"
             b"M5_C_ROMFS_PROGRAM_LOADED\nM5_C_USER_PAGES_READY\n"
             b"M5_C_RING3_STACK_OK\nM5_C_USER_VALUE=2026\n"
             b"M5_C_RING3_EXIT_OK\nM5_C_USER_FRAMES_RECLAIMED\n"
             b"M5_RUN_DONE\nM5_PROMPT> ")


def build(source: Path, dest: Path, root: Path, cache: Path,
          extra: list[str] | None = None) -> None:
    command = [sys.executable, str(ROOT / "scripts/build_boot.py"),
               "--source", str(source), "--out", str(dest),
               "--cache-dir", str(cache), "--work-dir", str(root),
               "--exception-idt", "--tss-ist", "--romfs-run-console", "--test-exit",
               *(extra or [])]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=180)
    if result.returncode or "ROMFS_CONTENT_SHA256=" not in result.stdout:
        raise AssertionError(f"M5-D1 build failed:\n{result.stdout}\n{result.stderr}")


def exercise(iso: Path, instructions: list[tuple[bytes, bytes]], expected_html: bytes,
             *, idle: bool = False) -> tuple[bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="m5-d-serial-") as temporary:
        debug = Path(temporary) / "debugcon.log"
        command = ["qemu-system-x86_64", "-M", "q35", "-m", "256M",
                   "-cdrom", str(iso), "-boot", "d", "-display", "none",
                   "-monitor", "none", "-net", "none", "-serial", "stdio",
                   "-debugcon", f"file:{debug}",
                   "-global", "isa-debugcon.iobase=0xe9",
                   "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04", "-no-reboot"]
        guest = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        def current() -> bytes:
            return debug.read_bytes() if debug.is_file() else b""
        def until(data: bytes, count: int = 1, seconds: float = 17) -> bytes:
            beginning = time.monotonic()
            while time.monotonic()-beginning < seconds:
                transcript = current()
                if transcript.count(data) >= count:
                    return transcript
                if guest.poll() is not None:
                    raise AssertionError(("early exit", guest.returncode, data, transcript))
                time.sleep(.018)
            raise AssertionError(("guest timeout", data, count, current()))
        try:
            assert until(BASE) == BASE, current()
            if idle:
                time.sleep(.6)
                assert guest.poll() is None and current() == BASE
                return current(), b""
            previous = BASE
            for payload, expected in instructions:
                target_count = current().count(expected) + 1
                for byte in payload:
                    assert guest.stdin is not None
                    guest.stdin.write(bytes((byte,)))
                    guest.stdin.flush()
                    time.sleep(.007)  # 16550 has a small FIFO; do not flood it
                result = until(expected, target_count)
                assert result.startswith(previous)
                previous = result
            stdout, stderr = guest.communicate(timeout=10)
            result = current()
            assert guest.returncode == SUCCESS_EXIT, (guest.returncode, result, stderr)
            assert result.endswith(b"M5_CONSOLE_EXIT\n" + expected_html), result
            assert b"M5_CONSOLE_FATAL" not in result and b"M4_UNKNOWN_SYSCALL_REJECTED" not in result
            return result, stdout
        finally:
            if guest.poll() is None:
                guest.kill()
                guest.communicate(timeout=4)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-m5-d1-") as temp:
        work = Path(temp)
        cache = Path(os.environ.get("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        source = ROOT / "examples/kernel.html"
        original = work / "original.iso"
        build(source, original, work, cache)
        commands = [
            (b"help\r", b"M5_HELP help ls cat /path run /path exit"),
            (b"ls\r", b"M5_FILE /apps/hello.hke"),
            (b"cat /welcome.txt\r", b"Hello from a real embedded ROMFS!"),
            (b"run /missing.hke\r", b"M5_ERR_NOT_FOUND"),
            (b"run /welcome.txt\r", b"M5_ERR_BAD_EXEC"),
            (b"run /../welcome.txt\r", b"M5_ERR_INVALID_PATH"),
            (b"run /\r", b"M5_ERR_INVALID_PATH"),
            (b"x"*96+b"\r", b"M5_ERR_INVALID_LINE"),
            (b"run /apps/hello.hke\r", APP_TRACE),
            (b"run /apps/hello.hke\r", APP_TRACE),
            (b"unknown\r", b"M5_ERR_UNKNOWN_COMMAND"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n"+HTML),
        ]
        output, echo = exercise(original, commands, HTML)
        assert output.count(APP_TRACE) == 2, output
        assert echo.count(b"M5_C_USER_VALUE=2026") == 2, "user output missing from real UART TX"
        assert output.count(b"M5_C_USER_FRAMES_RECLAIMED") == 2
        print("M5-D REAL UART HELP/LS/CAT/RUN TWICE/INVALID/EXIT + CPL3 + FRAME RECLAIM PASS")

        paused, _ = exercise(original, [], HTML, idle=True)
        assert paused == BASE
        print("M5-D NO UART INPUT DOES NOT AUTO-RUN USER PROGRAM OR HTML")

        original_html = source.read_text()
        assert original_html.count("Hello from HTML Kernel!") == 1
        changed_html = work / "changed.html"
        changed_html.write_text(original_html.replace("Hello from HTML Kernel!",
                                                      "M5-D HTML MUTATED!"))
        changed_html_iso = work / "changed-html.iso"
        build(changed_html, changed_html_iso, work, cache)
        modified_html = HTML.replace(b"Hello from HTML Kernel!", b"M5-D HTML MUTATED!")
        transcript, _ = exercise(changed_html_iso, [
            (b"run /apps/hello.hke\r", APP_TRACE),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + modified_html),
        ], modified_html)
        assert changed_html_iso.read_bytes() != original.read_bytes()
        assert HTML not in transcript
        print("M5-D HTML SOURCE MUTATION AFFECTS ACTUAL KERNEL OUTPUT")

        original_asm = (ROOT / "examples/user-programs/hello.S").read_text()
        assert original_asm.count("$2026") == 1
        mutated_source = work / "changed-user.S"
        mutated_source.write_text(original_asm.replace("$2026", "$2027"))
        mutated_app_iso = work / "changed-user.iso"
        build(source, mutated_app_iso, work, cache,
              ["--user-app-source", str(mutated_source)])
        changed_trace = APP_TRACE.replace(b"M5_C_USER_VALUE=2026", b"M5_C_USER_VALUE=2027")
        transcript, echo = exercise(mutated_app_iso, [
            (b"run /apps/hello.hke\r", changed_trace),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
        ], HTML)
        assert mutated_app_iso.read_bytes() != original.read_bytes()
        assert b"M5_C_USER_VALUE=2026" not in transcript
        assert b"M5_C_USER_VALUE=2027" in echo
        print("M5-D INDEPENDENT USER PROGRAM MUTATION 2026->2027 ON REAL UART+CPL3")

        from build_user_image import build as build_user_image
        bad_image_path = work / "bad-checksum.hke"
        good = build_user_image(ROOT / "examples/user-programs/hello.S",
                                work / "good.hke")
        bad_image_path.write_bytes(good[:36] + bytes([good[36] ^ 0x20]) + good[37:])
        bad_iso = work / "corrupted-app.iso"
        build(source, bad_iso, work, cache, ["--user-app-image", str(bad_image_path)])
        bad_trace, _ = exercise(bad_iso, [
            (b"run /apps/hello.hke\r", b"M5_ERR_BAD_EXEC"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
        ], HTML)
        assert b"M5_C_RING3_STACK_OK" not in bad_trace
        print("M5-D CORRUPTED HKEX REJECTED WITHOUT STOPPING SHELL")

        for opts in (
            ("--romfs-run-console",),
            ("--romfs-run-console", "--exception-idt"),
            ("--romfs-run-console", "--romfs-console", "--exception-idt", "--tss-ist"),
            ("--romfs-run-console", "--user-loader-probe", "--exception-idt", "--tss-ist"),
            ("--romfs-run-console", "--user-preempt-probe", "--exception-idt", "--tss-ist"),
        ):
            destination = work / "invalid.iso"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/build_boot.py"),
                                     "--out", str(destination), *opts],
                                    capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not destination.exists(), (opts, result.stderr)
        print("M5-D UNSAFE INCOMPATIBLE BUILDER MODES REJECTED")
    print("M5-D1 REAL COM1 SHELL -> SEPARATE CPL3 ROMFS EXECUTABLE ACCEPTANCE PASS")


if __name__ == "__main__":
    main()
