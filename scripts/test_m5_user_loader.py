#!/usr/bin/env python3
"""Native M5-C1 genuine Ring3 execution of an independently built ROMFS image."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
from build_user_image import build as build_app
from test_boot import ROOT, SUCCESS_EXIT, boot

HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
PREFIX = ("M3_TSS_IST_READY\nM3_IDT_READY\n"
          "M5_C_ROMFS_PROGRAM_LOADED\nM5_C_USER_PAGES_READY\n")
SUCCESS = (PREFIX + "M5_C_RING3_STACK_OK\nM5_C_USER_VALUE=2026\n"
           "M5_C_RING3_EXIT_OK\nM5_C_USER_FRAMES_RECLAIMED\n" + HTML)


def make_iso(source: Path, output: Path, work: Path, cache: Path,
             *extra: str) -> None:
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(output),
           "--cache-dir", str(cache), "--work-dir", str(work),
           "--exception-idt", "--tss-ist", "--user-loader-probe", "--test-exit", *extra]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f"M5-C1 ISO build failed: {result.stdout}\n{result.stderr}")
    assert "ROMFS_CONTENT_SHA256=" in result.stdout, result.stdout


def require(iso: Path, code: int, expected: str) -> str:
    exit_code, output = boot(iso, timeout=20)
    assert (exit_code, output) == (code, expected), (exit_code, output, code, expected)
    return output


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="htmlk-m5-c1-") as temp:
        work = Path(temp)
        cache = Path(os.getenv("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        source = ROOT / "examples/kernel.html"
        original = work / "original.iso"
        make_iso(source, original, work, cache)
        for repeat in range(3):
            require(original, SUCCESS_EXIT, SUCCESS)
        kernel_elf = original.with_suffix(".elf")
        nm = subprocess.run(["nm", str(kernel_elf)],capture_output=True,
                            text=True,check=True,timeout=20).stdout
        assert "htmlk_m4_user_code_begin" not in nm, "old hardcoded executable leaked into M5-C1"
        print("M5-C1 THREE REAL QEMU ROMFS IMAGE -> RING3 INT80 -> EXIT -> FRAME RECLAIM BOOTS PASS")

        orig_source = source.read_text()
        assert orig_source.count("Hello from HTML Kernel!") == 1
        changed_html = work / "changed-html.html"
        changed_html.write_text(orig_source.replace("Hello from HTML Kernel!",
                                                    "M5 HTML CODE MUTATED!"))
        iso_html = work / "changed-html.iso"
        make_iso(changed_html, iso_html, work, cache)
        require(iso_html, SUCCESS_EXIT, SUCCESS.replace("Hello from HTML Kernel!",
                                                     "M5 HTML CODE MUTATED!"))
        assert iso_html.read_bytes() != original.read_bytes()
        print("M5-C1 HTML SOURCE MUTATION PRODUCES DIFFERENT NATIVE GUEST OUTPUT")

        app_source = work / "modified-app.S"
        user_asm = (ROOT / "examples/user-programs/hello.S").read_text()
        assert user_asm.count("$2026") == 1
        app_source.write_text(user_asm.replace("$2026", "$2027"))
        iso_app = work / "changed-app.iso"
        make_iso(source, iso_app, work, cache, "--user-app-source", str(app_source))
        changed_program = SUCCESS.replace("M5_C_USER_VALUE=2026", "M5_C_USER_VALUE=2027")
        require(iso_app, SUCCESS_EXIT, changed_program)
        assert iso_app.read_bytes() != original.read_bytes()
        assert "M5_C_USER_VALUE=2026" not in changed_program
        print("M5-C1 INDEPENDENT USER ASSEMBLY MUTATION CHANGES REAL CPL3 SYSCALL OUTPUT")

        app_image = work / "app.hke"
        original_bytes = build_app(ROOT / "examples/user-programs/hello.S", app_image)
        for label, bad_image in (
            ("checksum", original_bytes[:40]+bytes([original_bytes[40]^1])+original_bytes[41:]),
            ("magic", b'?' + original_bytes[1:]),
            ("truncated", original_bytes[:-1]),
            ("reserved", original_bytes[:20] + b'\x01' + original_bytes[21:]),
        ):
            invalid = work / f"{label}.hke"
            invalid.write_bytes(bad_image)
            iso = work / f"bad-{label}.iso"
            make_iso(source, iso, work, cache, "--user-app-image", str(invalid))
            output = require(iso, 53, "M3_TSS_IST_READY\nM3_IDT_READY\nM5_C_IMAGE_INVALID\n")
            assert HTML not in output
        print("M5-C1 REAL QEMU CHECKSUM/MAGIC/TRUNCATION/RESERVED REJECTION EXIT53 PASS")

        bad_sys = work / "bad-syscall.iso"
        make_iso(source,bad_sys,work,cache,"--user-app-source",
                 str(ROOT / "examples/user-programs/bad-syscall.S"))
        output=require(bad_sys,53,PREFIX+"M4_UNKNOWN_SYSCALL_REJECTED\n")
        assert HTML not in output
        print("M5-C1 UNKNOWN RING3 SYSCALL DENIED ON REAL CPU")

        bad_io = work / "bad-io.iso"
        make_iso(source,bad_io,work,cache,"--user-app-source",
                 str(ROOT / "examples/user-programs/privileged-io.S"))
        code, output = boot(bad_io,timeout=20)
        assert code == 45 and re.fullmatch(
            re.escape(PREFIX) +
            r'M3_EXCEPTION V=0D\nM3_RIP=0x[0-9A-F]{16}\n'
            r'M3_ERROR=0x0000000000000000\n', output), (code,output)
        assert HTML not in output
        print("M5-C1 ACTUAL CPL3 PRIVILEGED OUTB -> CPU #GP FAIL-STOP EXIT45")

        for flags in (("--user-loader-probe",),
                      ("--user-app-source",str(app_source)),
                      ("--user-loader-probe","--romfs-console","--exception-idt","--tss-ist"),
                      ("--user-loader-probe","--user-preempt-probe","--exception-idt","--tss-ist"),
                      ("--user-loader-probe","--exception-idt","--tss-ist",
                       "--user-app-source",str(app_source),"--user-app-image",str(app_image))):
            nonexistent = work / "unsafe.iso"
            attempt = subprocess.run([sys.executable,str(ROOT / "scripts/build_boot.py"),
                                      "--out",str(nonexistent),*flags],
                                     capture_output=True,text=True,timeout=15)
            assert attempt.returncode != 0 and not nonexistent.exists(), (flags,attempt.stderr)
        print("M5-C1 UNSAFE/CONFLICTING BUILDER MODES FAIL CLOSED")
    print("M5-C1 ROMFS-LOADED REAL CPL3 PROGRAM ACCEPTANCE + REJECTION PASS")


if __name__ == '__main__':
    main()
