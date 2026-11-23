#!/usr/bin/env python3
"""One readable HTML program -> actual native Linux + Ring3 QEMU output.

The web UI is not the evidence here: each output is from real guest CPU UART.
"""
from __future__ import annotations

from pathlib import Path
import os
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import build, exercise, HTML

SOURCE = ROOT / "examples/human-agent-hello.html"
PRINT_3 = b"M5_C_USER_VALUE=3\n"
PRINT_5 = b"M5_C_USER_VALUE=5\n"
BIG = b"M5_C_USER_VALUE=4294967296\n"
DONE = b"M5_RUN_DONE\n"
CLEAN = b"M5_C_USER_FRAMES_RECLAIMED\n"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-human-agent-guest-") as root:
        work = Path(root)
        cache = Path(os.getenv("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        original = work / "original.iso"
        build(ROOT / "examples/kernel.html", original, work, cache,
              extra=["--user-app-html", str(SOURCE), "--user-fault-recover"])
        commands = [
            (b"help\r", b"M5_HELP help ls cat /path run /path exit"),
            (b"run /apps/hello.hke\r", DONE),
            (b"run /apps/hello.hke\r", DONE),
            (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
        ]
        trace, uart = exercise(original, commands, HTML)
        assert trace.count(PRINT_3) == uart.count(PRINT_3) == 6, trace
        assert trace.count(BIG) == uart.count(BIG) == 2, trace
        assert trace.count(CLEAN) == 2 and trace.count(DONE) == 2, trace
        print("HTML beginner program: 2 actual Ring3 QEMU runs, 6 counts, "
              "two 64-bit outputs, 6-frame reclaim each PASS", flush=True)

        source = SOURCE.read_text(encoding="utf-8")
        before = '<let name="count" type="u64" value="3"/>'
        after = '<let name="count" type="u64" value="5"/>'
        assert source.count(before) == 1
        changed = work / "changed.html"
        changed.write_text(source.replace(before, after), encoding="utf-8")
        modified = work / "modified.iso"
        build(ROOT / "examples/kernel.html", modified, work, cache,
              extra=["--user-app-html", str(changed), "--user-fault-recover"])
        changed_trace, changed_uart = exercise(
            modified, [
                (b"run /apps/hello.hke\r", DONE),
                (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
            ], HTML,
        )
        assert modified.read_bytes() != original.read_bytes()
        assert changed_trace.count(PRINT_5) == changed_uart.count(PRINT_5) == 3
        assert PRINT_3 not in changed_trace and PRINT_3 not in changed_uart
        assert changed_trace.count(BIG) == 1 and changed_trace.count(CLEAN) == 1
        print("Edited beginner HTML source -> different native ISO -> "
              "real CPU output 5 x 3, not 3 x 3 PASS")


if __name__ == "__main__":
    main()
