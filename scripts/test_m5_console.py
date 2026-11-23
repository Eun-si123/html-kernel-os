#!/usr/bin/env python3
"""M5-B: live BIOS QEMU 16550 UART RX, command grammar and file/HTML provenance."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from test_boot import ROOT, SUCCESS_EXIT

HTML = b"Hello from HTML Kernel!\nNative code, not a browser.\n"
READY = b"M5_CONSOLE_READY\nM5_PROMPT> "
WELCOME = b"Hello from a real embedded ROMFS!\n"


def build(source: Path, out: Path, cache: Path, work: Path, romfs: Path) -> None:
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(out), "--cache-dir", str(cache),
           "--work-dir", str(work), "--romfs-console", "--romfs-root", str(romfs),
           "--test-exit"]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if result.returncode or "ROMFS_CONTENT_SHA256=" not in result.stdout:
        raise AssertionError(f"M5-B build failed: {result.stdout}\n{result.stderr}")


def exercise(iso: Path, commands: list[tuple[bytes, bytes]], expected_html: bytes,
             *, idle_oracle: bool = False) -> tuple[bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="htmlk-m5-uart-") as temp:
        trace = Path(temp) / "debugcon.log"
        args = ["qemu-system-x86_64", "-M", "q35", "-m", "256M",
                "-cdrom", str(iso), "-boot", "d", "-display", "none",
                "-monitor", "none", "-net", "none", "-serial", "stdio",
                "-debugcon", f"file:{trace}",
                "-global", "isa-debugcon.iobase=0xe9",
                "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
                "-no-reboot"]
        guest = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        def received() -> bytes:
            return trace.read_bytes() if trace.is_file() else b""
        def until(needle: bytes, deadline: float = 18) -> bytes:
            start = time.monotonic()
            while time.monotonic() - start < deadline:
                data = received()
                if needle in data:
                    return data
                if guest.poll() is not None:
                    raise AssertionError(f"guest exited {guest.returncode} before {needle!r}: {data!r}")
                time.sleep(0.02)
            raise AssertionError(f"real QEMU did not reach {needle!r}: {received()!r}")
        try:
            assert until(READY) == READY
            if idle_oracle:
                time.sleep(0.65)
                assert guest.poll() is None, "guest cannot auto-accept a fake command"
                assert received() == READY, "guest cannot execute HTML without UART input"
                return received(), b""
            result_before = READY
            for command, expected in commands:
                assert guest.stdin is not None
                # Real UART has a 16-byte FIFO. A small byte gap is essential;
                # a one-shot host pipe write can overrun and spuriously lose keys.
                for byte in command:
                    guest.stdin.write(bytes((byte,)))
                    guest.stdin.flush()
                    time.sleep(0.007)
                result = until(expected)
                assert result.startswith(result_before)
                result_before = result
            stdout, stderr = guest.communicate(timeout=8)
            assert guest.returncode == SUCCESS_EXIT, (guest.returncode, received(), stderr)
            result = received()
            assert result.endswith(b"M5_CONSOLE_EXIT\n" + expected_html), result
            assert b"M5_CONSOLE_FATAL" not in result, result
            return result, stdout
        finally:
            if guest.poll() is None:
                guest.kill()
                guest.communicate(timeout=4)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-m5-console-") as temp:
        work = Path(temp)
        cache = Path(os.getenv("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        source = ROOT / "examples/kernel.html"
        romfs = ROOT / "examples/romfs"
        original = work / "serial-console.iso"
        build(source, original, cache, work, romfs)

        output, echoed = exercise(original, [
            (b"help\r", b"M5_HELP help ls cat /path exit"),
            (b"ls\r", b"M5_FILE /welcome.txt"),
            (b"cat /welcome.txt\r", b"M5_CAT_BEGIN /welcome.txt\n"+WELCOME+b"M5_CAT_END"),
            (b"cat /config/build.txt\r", b"M5_CAT_BEGIN /config/build.txt\nM5-A read-only native bytes\nM5_CAT_END"),
            (b"cat /missing.txt\r", b"M5_ERR_NOT_FOUND"),
            (b"cat /../welcome.txt\r", b"M5_ERR_INVALID_PATH"),
            (b"bogus\r", b"M5_ERR_UNKNOWN_COMMAND"),
            (b"x"*96+b"\r", b"M5_ERR_INVALID_LINE"),
            (b"ab\x01\r", b"M5_ERR_INVALID_LINE"),
            (b"hepl\b\bp\r", b"M5_HELP help ls cat /path exit"),
            (b"exit\r", b"M5_CONSOLE_EXIT"),
        ], HTML)
        assert echoed.startswith(READY)
        assert b"help\n" in echoed and b"cat /welcome.txt\n" in echoed
        assert output.count(b"M5_ERR_INVALID_LINE") == 2
        assert output.count(b"M5_CAT_BEGIN") == 2
        print("M5-B ACTUAL UART RX HELP/LS/CAT/EXIT, ERRORS, LIMITS AND RECOVERY PASS")

        paused, _ = exercise(original, [], HTML, idle_oracle=True)
        assert paused == READY
        print("M5-B IDLE: NO USER UART INPUT -> NO FAKE PROGRESS/HTML")

        altered_files = work / "mutated-romfs"
        shutil.copytree(romfs, altered_files)
        (altered_files / "welcome.txt").write_text("CONSOLE FILE MUTATED!\n")
        altered_iso = work / "altered-romfs.iso"
        build(source, altered_iso, cache, work, altered_files)
        output, _ = exercise(altered_iso, [
            (b"cat /welcome.txt\r", b"M5_CAT_BEGIN /welcome.txt\nCONSOLE FILE MUTATED!\nM5_CAT_END"),
            (b"exit\r", b"M5_CONSOLE_EXIT"),
        ], HTML)
        assert original.read_bytes() != altered_iso.read_bytes()
        assert WELCOME not in output
        print("M5-B CHANGED ROMFS BYTES -> REBUILT ISO -> TRUE UART CONTENT PASS")

        modified_source = work / "changed.html"
        html = source.read_text()
        assert html.count("Hello from HTML Kernel!") == 1
        modified_source.write_text(html.replace("Hello from HTML Kernel!", "M5 SOURCE MUTATED!"))
        changed_html_iso = work / "changed-html.iso"
        build(modified_source, changed_html_iso, cache, work, romfs)
        modified_html_output = HTML.replace(b"Hello from HTML Kernel!", b"M5 SOURCE MUTATED!")
        output, _ = exercise(changed_html_iso, [
            (b"exit\r", b"M5_CONSOLE_EXIT"),
        ], modified_html_output)
        assert original.read_bytes() != changed_html_iso.read_bytes()
        assert HTML not in output
        print("M5-B CHANGED HTML SOURCE -> REBUILT ISO -> TRUE CPU EXECUTION PASS")

        invalid = work / "invalid.iso"
        for flags in (("--romfs-console", "--romfs-probe"),
                      ("--romfs-console", "--exception-idt"),
                      ("--romfs-negative", "--romfs-console")):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/build_boot.py"),
                                     "--out", str(invalid), *flags],
                                    capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not invalid.exists(), (flags, result.stderr)
        print("M5-B EXCLUSIVE UNSAFE BUILD MODES REJECTED")
    print("M5-B REAL UART CONSOLE NATIVE QEMU PROOF PASS")


if __name__ == "__main__":
    main()
