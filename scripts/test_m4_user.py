#!/usr/bin/env python3
"""Actual QEMU CPL3 -> INT0x80 -> CPL0 -> CPL3 and supervisor/RO protections."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT, boot

PREFIX = ("M3_TSS_IST_READY\nM3_IDT_READY\nM4_USER_PAGE_TABLES_READY\n"
          "M4_RING3_CPL3_SYSCALL_OK\n")
BASE = "M3_TSS_IST_READY\nM3_IDT_READY\nM4_USER_PAGE_TABLES_READY\n"
FINISH = "M4_RING3_EXIT_OK\nM4_RING3_MAIN_RESTORED\n"
HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M4 USER HTML SOURCE MUTATED!\nNative code, not a browser.\n"

def build(source, out, work, *, negative=None):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(out),
           "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                        str(ROOT / "build/.cache")),
           "--work-dir", str(work), "--test-exit",
           "--exception-idt", "--tss-ist", "--user-probe"]
    if negative:
        cmd.append("--" + negative)
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise AssertionError(result.stdout + "\n" + result.stderr)

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-ring3-") as tmp:
        work = Path(tmp)
        src = ROOT / "examples/kernel.html"
        first = work / "normal.iso"
        build(src, first, work)
        for i in range(2):
            code, output = boot(first, timeout=20)
            if (code, output) != (SUCCESS_EXIT, PREFIX + FINISH + HTML):
                raise AssertionError(f"ring3/syscall run {i} failed: {code}, {output!r}")
        print("M4 REAL QEMU CPL3 SYSCALL/IRET/FRAME RECLAIM x2 PASS")

        original = src.read_text(encoding="utf-8")
        assert original.count("Hello from HTML Kernel!") == 1
        changed_src = work / "changed.html"
        changed_src.write_text(original.replace(
            "Hello from HTML Kernel!", "M4 USER HTML SOURCE MUTATED!"),
            encoding="utf-8")
        changed_iso = work / "changed.iso"
        build(changed_src, changed_iso, work)
        code, output = boot(changed_iso, timeout=20)
        assert (code, output) == (SUCCESS_EXIT, PREFIX + FINISH + CHANGED), (
            code, output)
        assert first.read_bytes() != changed_iso.read_bytes()
        assert HTML not in output
        print("M4 REAL RING3 ISO HTML MUTATION/STALENESS NEGATIVE PASS")

        bad_call = work / "bad-call.iso"
        build(src, bad_call, work, negative="user-bad-syscall")
        code, output = boot(bad_call, timeout=20)
        assert (code, output) == (53, PREFIX + "M4_UNKNOWN_SYSCALL_REJECTED\n"), (code, output)
        print("M4 RING3 INVALID SYSCALL REAL CPU FAIL-CLOSED PASS")

        privileged = work / "privileged-io.iso"
        build(src, privileged, work, negative="user-privileged-io")
        code, output = boot(privileged, timeout=20)
        assert code == 45, (code, output)
        assert re.fullmatch(PREFIX +
            "M3_EXCEPTION V=0D\nM3_RIP=0x[0-9A-F]{16}\n"
            "M3_ERROR=0x0000000000000000\n", output), output
        print("M4 REAL CPL3 PORT I/O DENIED BY CPU #GP PASS")

        for opt, error_code, fault_address in (
                ("user-read-kernel", "5", "FFFFFFFF80001000"),
                ("user-write-code", "7", "0000400000000000")):
            iso = work / (opt + ".iso")
            build(src, iso, work, negative=opt)
            code, output = boot(iso, timeout=20)
            pattern = (PREFIX + "M3_IST_PF_STACK_OK\n" +
                "M3_EXCEPTION V=0E\nM3_RIP=0x[0-9A-F]{16}\n" +
                "M3_ERROR=0x000000000000000" + error_code + "\n" +
                "M3_CR2=0x" + fault_address + "\n")
            assert code == 45 and re.fullmatch(pattern, output), (opt, code, output)
            assert FINISH not in output and HTML not in output
            print("M4 REAL RING3 HARDWARE PERMISSION REJECTED:", opt)

        invalid_combinations = [
            ["--user-probe"], ["--user-probe", "--exception-idt"],
            ["--user-bad-syscall"], ["--user-write-code"],
            ["--user-probe", "--exception-idt", "--tss-ist", "--paging-probe"],
            ["--user-probe", "--exception-idt", "--tss-ist", "--preempt-probe"],
            ["--user-probe", "--exception-idt", "--tss-ist",
             "--user-write-code", "--user-read-kernel"]
        ]
        for flags in invalid_combinations:
            missing = work / "invalid.iso"
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--out", str(missing), *flags],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not missing.exists(), flags
        print("M4 UNSUPPORTED RING3 BUILDER COMBINATIONS REJECTED")
    print("M4-C1 REAL CPL3 + INT0X80 + PERMISSIONS QEMU GATE PASS")

if __name__ == "__main__":
    main()
