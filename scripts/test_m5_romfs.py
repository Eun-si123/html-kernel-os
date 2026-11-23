#!/usr/bin/env python3
"""M5-A real x86-64 BIOS/QEMU ROMFS reads, provenance and rejection oracles."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from test_boot import ROOT, SUCCESS_EXIT, boot

HTML = "Hello from HTML Kernel!\nNative code, not a browser.\n"
PREFIX = ("M5_ROMFS_VALID\nM5_ROMFS_WELCOME_BEGIN\n"
          "Hello from a real embedded ROMFS!\n"
          "M5_ROMFS_WELCOME_END\nM5_ROMFS_CONFIG_BEGIN\n"
          "M5-A read-only native bytes\nM5_ROMFS_CONFIG_END\n")


def build(source: Path, iso: Path, cache: Path, work: Path, romfs: Path, negative=False):
    cmd = [sys.executable, str(ROOT / "scripts/build_boot.py"),
           "--source", str(source), "--out", str(iso),
           "--cache-dir", str(cache), "--work-dir", str(work),
           "--romfs-root", str(romfs), "--romfs-probe", "--test-exit"]
    if negative: cmd.append("--romfs-negative")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f"M5 build failed: {result.stdout}\n{result.stderr}")
    assert 'ROMFS_CONTENT_SHA256=' in result.stdout, result.stdout


def main():
    with tempfile.TemporaryDirectory(prefix="htmlk-m5-") as temp:
        work = Path(temp)
        cache = Path(os.environ.get("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
        source = ROOT / "examples/kernel.html"
        romfs = ROOT / "examples/romfs"
        native = work / "romfs.iso"
        build(source, native, cache, work, romfs)
        code, output = boot(native, timeout=20)
        assert (code, output) == (SUCCESS_EXIT, PREFIX + "M5_ROMFS_PASS\n" + HTML), (code, output)
        print("M5-A REAL QEMU ELF ROMFS READ + GENERATED HTML PASS")

        mutated = work / "mutated"
        shutil.copytree(romfs, mutated)
        (mutated / "welcome.txt").write_text("ROMFS ASSET WAS MUTATED!\n")
        changed = work / "changed.iso"
        build(source, changed, cache, work, mutated)
        code, output = boot(changed, timeout=20)
        expected = PREFIX.replace("Hello from a real embedded ROMFS!\n",
                                  "ROMFS ASSET WAS MUTATED!\n") + "M5_ROMFS_PASS\n" + HTML
        assert (code, output) == (SUCCESS_EXIT, expected), (code, output)
        assert native.read_bytes() != changed.read_bytes()
        assert "Hello from a real embedded ROMFS!" not in output
        print("M5-A ROMFS ASSET CHANGES REAL ISO OUTPUT; STALE ASSET REJECTED")

        changed_html = work / "changed-source.html"
        original_html = source.read_text()
        assert original_html.count("Hello from HTML Kernel!") == 1
        changed_html.write_text(original_html.replace(
            "Hello from HTML Kernel!", "M5 HTML SOURCE WAS MUTATED!"))
        changed_source_iso = work / "changed-source.iso"
        build(changed_html, changed_source_iso, cache, work, romfs)
        code, output = boot(changed_source_iso, timeout=20)
        assert (code, output) == (SUCCESS_EXIT, PREFIX + "M5_ROMFS_PASS\n" +
                                  HTML.replace("Hello from HTML Kernel!",
                                               "M5 HTML SOURCE WAS MUTATED!")), (code, output)
        assert changed_source_iso.read_bytes() != native.read_bytes()
        assert "Hello from HTML Kernel!" not in output
        print("M5-A CHANGED HTML SOURCE RECOMPILES INTO DIFFERENT NATIVE ISO")

        denial = work / "negative.iso"
        build(source, denial, cache, work, romfs, negative=True)
        code, output = boot(denial, timeout=20)
        assert (code, output) == (57, PREFIX + "M5_ROMFS_DENIED\nM5_ROMFS_FATAL\n"), (code, output)
        assert HTML not in output
        print("M5-A REAL QEMU FAIL-CLOSED NEGATIVE EXIT 57, NO HTML")

        wrong = work / "invalid.iso"
        for flags in (("--romfs-negative",), ("--romfs-probe", "--exception-idt")):
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_boot.py"),
                "--out", str(wrong), *flags], capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and not wrong.exists(), (flags, result.stderr)
        print("M5-A BUILDER CONFLICTS REJECTED")
    print("M5-A BOUNDED ROMFS NATIVE PROOF PASS")


if __name__ == "__main__":
    main()
