#!/usr/bin/env python3
"""M4-A: prove actual ring-0 stack switching and reject invalid task transitions."""
from pathlib import Path
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT, boot

HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
CHANGED = "M4 HTML SOURCE CHANGED!\nNative code, not a browser.\n"
TASKS = "".join(f"M4_TASK_{id}_{turn}\n" for turn in range(3) for id in "AB")
DONE = "M4_TASKS_DONE\n"

def build(source: Path, iso: Path, cache: Path, work: Path, *, negative=False):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", str(cache), "--work-dir", str(work),
           "--test-exit", "--task-probe"]
    if negative:
        cmd.append("--task-negative-test")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f"M4 build failed: {result.stdout}\n{result.stderr}")

def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-m4-") as d:
        work = Path(d)
        cache = Path(__import__("os").environ.get("HTMLK_CACHE_DIR",
                                                str(ROOT / "build/.cache")))
        for optimization in ("-O0", "-O3"):
            executable = work / f"task-model-{optimization}"
            cmd = ["gcc", "-std=c11", optimization, "-fsanitize=undefined",
                   "-fno-sanitize-recover=all", "-Wall", "-Wextra", "-Werror",
                   "-I", str(ROOT / "boot"),
                   str(ROOT / "boot/task_model.c"),
                   str(ROOT / "tests/native/test_task_model.c"),
                   "-o", str(executable)]
            subprocess.run(cmd, check=True, timeout=30)
            run = subprocess.run([str(executable)], capture_output=True,
                                 text=True, timeout=10, check=True)
            assert run.stdout == "M4 MODEL TRANSITIONS + INVALID STATES PASS\n"
        print("M4 HOST MODEL -O0/-O3 UBSAN NEGATIVE STATES PASS")

        source = ROOT / "examples/kernel.html"
        normal = work / "normal.iso"
        build(source, normal, cache, work)
        code, output = boot(normal, timeout=20)
        assert (code, output) == (SUCCESS_EXIT, TASKS + DONE + HTML), (code, output)
        print("M4 REAL QEMU TWO STACKS/COOPERATIVE SCHEDULER PASS")

        changed = work / "changed.html"
        original = source.read_text()
        assert original.count("Hello from HTML Kernel!") == 1
        changed.write_text(original.replace("Hello from HTML Kernel!",
                                            "M4 HTML SOURCE CHANGED!"))
        changed_iso = work / "changed.iso"
        build(changed, changed_iso, cache, work)
        code, output = boot(changed_iso, timeout=20)
        assert (code, output) == (SUCCESS_EXIT, TASKS + DONE + CHANGED), (code, output)
        assert changed_iso.read_bytes() != normal.read_bytes()
        assert HTML not in output
        print("M4 HTML SOURCE MUTATION/STALE-OUTPUT NEGATIVE PASS")

        rejected = work / "negative.iso"
        build(source, rejected, cache, work, negative=True)
        code, output = boot(rejected, timeout=20)
        expected = ("M4_TASK_NEGATIVE_REJECTED\n" + TASKS +
                    "M4_TASK_RESTART_REJECTED\n" + DONE + HTML)
        assert (code, output) == (SUCCESS_EXIT, expected), (code, output)
        print("M4 REAL QEMU DUPLICATE/OOB/DEAD-TASK REJECTION PASS")

        invalid_iso = work / "invalid.iso"
        result = subprocess.run([
            sys.executable, str(ROOT / "scripts/build_boot.py"),
            "--source", str(source), "--out", str(invalid_iso),
            "--task-negative-test"], capture_output=True, text=True, timeout=15)
        assert result.returncode != 0 and not invalid_iso.exists()
        print("M4 UNSAFE BUILDER FLAGS REJECTED")
    print("M4-A NATIVE COOPERATIVE TASK PROOF PASS")

if __name__ == "__main__":
    main()
