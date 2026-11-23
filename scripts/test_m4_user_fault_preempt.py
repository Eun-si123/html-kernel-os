#!/usr/bin/env python3
"""M4-D2: actual IRQ-preempted CPL3 A faults on IST2, B survives on saved CR3."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT
from test_m4_user_preempt import boot, txt, PREFIX, START, HTML

HEAD = ("M4_D1_USER_A_0\nM4_D1_USER_B_0\n"
        "M4_D1_USER_A_1\nM4_D1_USER_B_1\n")
FAULT = ("M3_IST_PF_STACK_OK\nM4_D2_A_PF_ERROR_5\n"
         "M4_D2_A_RECLAIMED\n")
SURVIVE = ("M4_D1_USER_B_2\nM4_D1_USER_B_3\nM4_D1_USER_B_4\n"
           "M4_D2_CPL3_FAULT_SURVIVOR_PASS\n"
           "M4_D1_ALL_FRAMES_RECLAIMED\n")
ALTERED = "D2 SURVIVOR HTML SOURCE CHANGED!\nNative code, not a browser.\n"

def build(source: Path, iso: Path, work: Path, flags=()):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", os.environ.get("HTMLK_CACHE_DIR",
                                         str(ROOT / "build/.cache")),
           "--work-dir", str(work), "--test-exit", "--exception-idt",
           "--tss-ist", "--user-preempt-probe", "--user-preempt-fault",
           *flags]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                       text=True, timeout=180)
    assert p.returncode == 0, (p.stdout, p.stderr)

def exact(iso: Path, log: str, times=1):
    for i in range(times):
        r = boot(iso)
        assert (r.returncode, txt(r)) == (SUCCESS_EXIT, log), (
            i, r.returncode, txt(r), r.stderr)
def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-d2-") as tmp:
        work = Path(tmp)
        source = ROOT / "examples/kernel.html"
        iso = work / "normal.iso"
        build(source, iso, work)
        expected = START + HEAD + FAULT + SURVIVE + HTML
        exact(iso, expected, times=3)
        print("M4-D2 THREE REPEATED REAL QEMU CPL3 PREEMPT + IST2 FAULT SURVIVAL PASS")

        original = source.read_text(encoding="utf-8")
        assert original.count("Hello from HTML Kernel!") == 1
        changed = work / "changed.html"
        changed.write_text(original.replace(
            "Hello from HTML Kernel!", "D2 SURVIVOR HTML SOURCE CHANGED!"),
            encoding="utf-8")
        changed_iso = work / "changed.iso"
        build(changed, changed_iso, work)
        exact(changed_iso, START + HEAD + FAULT + SURVIVE + ALTERED)
        assert iso.read_bytes() != changed_iso.read_bytes()
        assert HTML not in txt(boot(changed_iso))
        print("M4-D2 CHANGED HTML -> DIFFERENT ISO -> REAL SURVIVOR OUTPUT PASS")

        bad = work / "unexpected-b-fault.iso"
        build(source, bad, work, ("--user-preempt-survivor-fault",))
        r = boot(bad)
        assert r.returncode == 45, (r.returncode, txt(r))
        prefix = START + HEAD + FAULT + "M4_D1_USER_B_2\n"
        assert re.fullmatch(prefix + r"M3_EXCEPTION V=0D\n"
                            r"M3_RIP=0x[0-9A-F]{16}\n"
                            r"M3_ERROR=0x0000000000000000\n", txt(r)), txt(r)
        assert "M4_D2_CPL3_FAULT_SURVIVOR_PASS" not in txt(r)
        print("M4-D2 UNEXPECTED B CPL3 FAULT IS FAIL-STOP, NO A REUSE")
        for extra in (
            ("--user-preempt-fault",),
            ("--user-preempt-survivor-fault",),
            ("--user-preempt-probe", "--user-preempt-fault"),
            ("--user-preempt-probe", "--user-preempt-survivor-fault",
             "--exception-idt", "--tss-ist", "--test-exit"),
            ("--user-preempt-probe", "--user-preempt-fault",
             "--user-preempt-mask", "--exception-idt", "--tss-ist",
             "--test-exit"),
            ("--user-preempt-probe", "--user-preempt-fault",
             "--user-preempt-bad-frame", "--exception-idt", "--tss-ist",
             "--test-exit"),
        ):
            invalid = work / "invalid.iso"
            p = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_boot.py"),
                 "--out", str(invalid), *extra],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            assert p.returncode != 0 and not invalid.exists(), (extra, p.stderr)
        print("M4-D2 INVALID NEGATIVE BUILDER MODES REJECTED")
    print("M4-D2 CONTINUOUS USER TASK FAULT CONTAINMENT E2E PASS")

if __name__ == "__main__":
    main()
