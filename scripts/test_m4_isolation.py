#!/usr/bin/env python3
"""Real CPU single-core ring3 process fault survival: two distinct CR3 roots."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT, boot

BASE = ("M3_TSS_IST_READY\nM3_IDT_READY\n"
        "M4_ISO_TWO_CR3_READY\nM4_ISO_A_CPL3_READY\n")
SURVIVOR = ("M4_ISO_A_RECLAIMED\nM4_ISO_B_CPL3_SYSCALL_OK\n"
            "M4_ISO_B_EXIT_OK\nM4_ISO_NO_FRAME_LEAK\n")
ORIGINAL = "Hello from HTML Kernel!\nNative code, not a browser.\n"
MODIFIED = "M4 ISOLATION HTML MUTATED!\nNative code, not a browser.\n"

def build(source, iso, work, extra=()):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                        str(ROOT / "build/.cache")),
           "--work-dir", str(work), "--exception-idt", "--tss-ist",
           "--user-isolation-probe", "--test-exit", *extra]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, r.stdout + "\n" + r.stderr

def exact(iso, expected, repeats=1):
    for i in range(repeats):
        result = boot(iso, timeout=20)
        assert result == (SUCCESS_EXIT, expected), (i, result)

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-iso-") as tmp:
        work = Path(tmp)
        src = ROOT / "examples/kernel.html"
        normal = work / "normal.iso"
        build(src, normal, work)
        exact(normal, BASE + "M3_IST_PF_STACK_OK\n" +
              "M4_ISO_A_PF_ERROR_5\n" + SURVIVOR + ORIGINAL, repeats=3)
        print("M4 REAL QEMU THREE REPEATED CPL3 A-PF/B-SURVIVES BOOTS PASS")

        changed = work / "changed.html"
        original = src.read_text(encoding="utf-8")
        assert original.count("Hello from HTML Kernel!") == 1
        changed.write_text(original.replace(
            "Hello from HTML Kernel!", "M4 ISOLATION HTML MUTATED!"),
            encoding="utf-8")
        changed_iso = work / "changed.iso"
        build(changed, changed_iso, work)
        exact(changed_iso, BASE + "M3_IST_PF_STACK_OK\n" +
              "M4_ISO_A_PF_ERROR_5\n" + SURVIVOR + MODIFIED)
        assert normal.read_bytes() != changed_iso.read_bytes()
        print("M4 CPL3 SURVIVOR HTML SOURCE -> NEW ISO -> REAL OUTPUT PASS")

        for mode, prefix in (
                ("--user-isolation-gp", "M4_ISO_A_GP_ERROR_0\n"),
                ("--user-isolation-ro",
                 "M3_IST_PF_STACK_OK\nM4_ISO_A_PF_ERROR_7\n")):
            iso = work / (mode[2:] + ".iso")
            build(src, iso, work, (mode,))
            exact(iso, BASE + prefix + SURVIVOR + ORIGINAL, repeats=2)
            print("M4 CPU FAULT SURVIVOR PASS:", mode)

        forged = work / "forged.iso"
        build(src, forged, work, ("--user-isolation-forged",))
        result = boot(forged, timeout=20)
        assert result == (
            55, "M3_TSS_IST_READY\nM3_IDT_READY\n"
                "M4_ISO_FORGED_KERNEL_CONTEXT_REJECTED\n"), result
        print("M4 FORGED KERNEL CS NEVER ACCEPTED AS USER FAULT")

        broken = work / "survivor-fault.iso"
        build(src, broken, work, ("--user-isolation-survivor-fault",))
        code, output = boot(broken, timeout=20)
        pattern = (BASE + "M3_IST_PF_STACK_OK\nM4_ISO_A_PF_ERROR_5\n" +
                   "M4_ISO_A_RECLAIMED\nM4_ISO_B_CPL3_SYSCALL_OK\n" +
                   "M3_EXCEPTION V=0D\nM3_RIP=0x[0-9A-F]{16}\n" +
                   "M3_ERROR=0x0000000000000000\n")
        assert code == 45 and re.fullmatch(pattern, output), (code, output)
        assert "M4_ISO_NO_FRAME_LEAK" not in output
        assert ORIGINAL not in output
        print("M4 SECOND USER FAULT FAIL-STOPS, NEVER REUSES A RECOVERY PATH")

        for bad in (
            ("--user-isolation-probe",),
            ("--user-isolation-gp",),
            ("--user-isolation-probe", "--exception-idt"),
            ("--user-isolation-probe", "--exception-idt", "--tss-ist",
             "--user-probe"),
            ("--user-isolation-probe", "--exception-idt", "--tss-ist",
             "--preempt-probe"),
            ("--user-isolation-probe", "--exception-idt", "--tss-ist",
             "--user-isolation-gp", "--user-isolation-ro"),
        ):
            invalid = work / "invalid.iso"
            r = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--out", str(invalid), *bad],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            assert r.returncode != 0 and not invalid.exists(), bad
        print("M4 UNSUPPORTED ISOLATION BUILDER COMBINATIONS REJECTED")
    print("M4-C2 QEMU TWO CR3 / USER FAULT CONTAINMENT E2E PASS")

if __name__ == "__main__":
    main()
