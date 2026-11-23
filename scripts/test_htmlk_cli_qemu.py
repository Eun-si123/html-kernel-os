#!/usr/bin/env python3
"""Developer CLI-built HKEX -> genuine boot ISO -> CPL3 CPU UART output.

This test ensures the user-target build is genuinely run by real kernel CPU.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import build, exercise, HTML

CLI = ROOT / "scripts/htmlk.py"
SOURCE = ROOT / "examples/human-agent-hello.html"


def cli_build(source: Path, dest: Path) -> bytes:
    result = subprocess.run(
        [sys.executable, str(CLI), "build", str(source), "--target", "user",
         "--out", str(dest), "--json"],
        capture_output=True, timeout=30, cwd=ROOT,
    )
    if result.returncode:
        raise AssertionError((result.returncode, result.stdout, result.stderr))
    import json
    record = json.loads(result.stdout)
    image = dest.read_bytes()
    assert record["ok"] and record["target"] == "user"
    assert record["sha256"] == hashlib.sha256(image).hexdigest()
    assert image.startswith(b"HKEX") and len(image) <= 4096
    return image


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-dev-cli-native-") as td:
        workspace = Path(td)
        cache = Path(os.getenv("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        app = workspace / "hello.hke"
        original = cli_build(SOURCE, app)
        iso = workspace / "original.iso"
        build(ROOT / "examples/kernel.html", iso, workspace, cache,
              extra=["--user-app-image", str(app), "--user-app-html-proof",
                     str(SOURCE), "--user-fault-recover"])
        commands = [
            (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
            (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
        ]
        trace, uart = exercise(iso, commands, HTML)
        assert trace.count(b"M5_C_USER_VALUE=3\n") == 6
        assert uart.count(b"M5_C_USER_VALUE=3\n") == 6
        assert trace.count(b"M5_C_USER_VALUE=4294967296\n") == 2
        assert trace.count(b"M5_C_USER_FRAMES_RECLAIMED\n") == 2
        print("M2-UX2 CLI BUILD -> actual QEMU CPL3 COM1 2 executions + frame reclaim PASS")

        # Negative: the same prebuilt HKEX without byte-exact source proof
        # retains the older assembly/legacy syscall bound; no silent ABI widen.
        legacy_iso = workspace / "legacy-prebuilt.iso"
        build(ROOT / "examples/kernel.html", legacy_iso, workspace, cache,
              extra=["--user-app-image", str(app), "--user-fault-recover"])
        legacy_out, legacy_uart = exercise(legacy_iso, [
            (b"run /apps/hello.hke\r", b"M5_ERR_USER_SYSCALL\n"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
        ], HTML)
        assert b"M5_C_USER_VALUE=4294967296\n" not in legacy_out
        assert legacy_out.count(b"M5_C_USER_VALUE=3\n") == 1
        assert b"M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n" in legacy_out
        assert b"M5_RUN_DONE\n" not in legacy_out
        print("M2-UX2 no HTML source proof: original legacy ABI denial and reclaim PASS")

        src = workspace / "changed.html"
        content = SOURCE.read_text(encoding="utf-8")
        assert content.count('name="count" type="u64" value="3"') == 1
        src.write_text(content.replace('name="count" type="u64" value="3"',
                                       'name="count" type="u64" value="5"'),
                       encoding="utf-8")
        second = workspace / "changed.hke"
        changed = cli_build(src, second)
        assert original != changed
        changed_iso = workspace / "changed.iso"
        build(ROOT / "examples/kernel.html", changed_iso, workspace, cache,
              extra=["--user-app-image", str(second), "--user-app-html-proof",
                     str(src), "--user-fault-recover"])
        changed_trace, changed_uart = exercise(
            changed_iso, [
                (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
                (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
            ], HTML,
        )
        assert changed_iso.read_bytes() != iso.read_bytes()
        assert changed_trace.count(b"M5_C_USER_VALUE=5\n") == 3
        assert changed_uart.count(b"M5_C_USER_VALUE=5\n") == 3
        assert b"M5_C_USER_VALUE=3\n" not in changed_trace
        assert b"M5_C_USER_FRAMES_RECLAIMED\n" in changed_trace
        print("M2-UX2 modified HTML -> CLI HKEX -> different ISO -> "
              "real CPU changed output 5, no stale 3 PASS")

        # Proof is a build-time provenance assertion, NOT a forged feature
        # flag or magic filename: mismatched source, modified image, symlink
        # and proof without image all must fail *before* creating an ISO.
        def reject(label: str, *arguments: str) -> None:
            dest = workspace / (label + ".iso")
            process = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--source", str(ROOT / "examples/kernel.html"),
                "--exception-idt", "--tss-ist", "--romfs-run-console",
                "--cache-dir", str(cache), "--work-dir", str(workspace),
                "--out", str(dest), *arguments,
            ], capture_output=True, timeout=35)
            assert process.returncode != 0 and not dest.exists(), (
                label, process.returncode, process.stdout[-500:], process.stderr[-500:])

        reject("source-mismatch", "--user-app-image", str(app),
               "--user-app-html-proof", str(src))
        broken = workspace / "corrupt.hke"
        malformed = bytearray(original)
        malformed[-1] ^= 0x20
        broken.write_bytes(malformed)
        reject("tampered-image", "--user-app-image", str(broken),
               "--user-app-html-proof", str(SOURCE))
        sym = workspace / "symlink-source.html"
        sym.symlink_to(SOURCE)
        reject("symlink-proof", "--user-app-image", str(app),
               "--user-app-html-proof", str(sym))
        reject("missing-image", "--user-app-html-proof", str(SOURCE))
        reject("two-app-modes", "--user-app-html", str(SOURCE),
               "--user-app-image", str(app), "--user-app-html-proof", str(SOURCE))
        print("M2-UX2 forged provenance/source/image/symlink/mode denials PASS")



if __name__ == "__main__":
    main()
