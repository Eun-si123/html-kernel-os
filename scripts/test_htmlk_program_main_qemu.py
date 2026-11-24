#!/usr/bin/env python3
"""M2-UX3 new program/main user syntax -> genuine native CPL3 and changed CPU output."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import build, exercise, HTML

APP = ROOT / "examples/human-agent-program.html"
OLD_VALUE = b"M5_C_USER_VALUE=6\n"
NEW_VALUE = b"M5_C_USER_VALUE=10\n"
LARGE = b"M5_C_USER_VALUE=4294967296\n"
RECLAIM = b"M5_C_USER_FRAMES_RECLAIMED\n"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-program-root-qemu-") as temp:
        work = Path(temp)
        cache = Path(os.environ.get("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        original = work / "program.iso"
        build(ROOT / "examples/kernel.html", original, work, cache,
              extra=["--user-app-html", str(APP), "--user-fault-recover"])
        trace, uart = exercise(original, [
            (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
            (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n"+HTML),
        ], HTML)
        assert trace.count(OLD_VALUE) == uart.count(OLD_VALUE) == 6
        assert trace.count(LARGE) == uart.count(LARGE) == 2
        assert trace.count(RECLAIM) == 2
        print("M2-UX3 <program><main> native QEMU Ring3 double-run + reclaim PASS")

        text = APP.read_text(encoding="utf-8")
        before = 'name="count" type="u64" value="3"'
        assert text.count(before) == 1
        changed = work / "changed.html"
        changed.write_text(text.replace(before,
                                        'name="count" type="u64" value="5"'),
                           encoding="utf-8")
        changed_iso = work / "changed.iso"
        build(ROOT / "examples/kernel.html", changed_iso, work, cache,
              extra=["--user-app-html", str(changed), "--user-fault-recover"])
        changed_trace, changed_uart = exercise(changed_iso, [
            (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
            (b"exit\r", b"M5_CONSOLE_EXIT\n"+HTML),
        ], HTML)
        assert original.read_bytes() != changed_iso.read_bytes()
        assert changed_trace.count(NEW_VALUE) == changed_uart.count(NEW_VALUE) == 3
        assert OLD_VALUE not in changed_trace and OLD_VALUE not in changed_uart
        assert changed_trace.count(LARGE) == 1
        assert changed_trace.count(RECLAIM) == 1
        print("M2-UX3 changed program/main HTML -> distinct ISO -> genuine CPL3 values 10 PASS")

        # Nonkernel root can never silently boot as a privileged kernel.
        generated = work / "must-not-exist.c"
        denied = subprocess.run([
            sys.executable, str(ROOT / "compiler/htmlk.py"), str(APP),
            "--target", "kernel", "--out", str(generated),
        ], capture_output=True, timeout=12)
        assert denied.returncode != 0 and not generated.exists()
        assert b"for Linux or Ring3 user apps" in denied.stderr, denied.stderr
        print("M2-UX3 illegal program/main native kernel target denied before output PASS")


if __name__ == "__main__":
    main()
