#!/usr/bin/env python3
"""Build an actual BIOS/UEFI Limine x86-64 ISO from HTML-generated code."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LIMINE_VERSION = "v12.11.1"
LIMINE_TAR_SHA256 = "953aba25c23abc6d6b4e85e20ec8b9f3a8605450a26997103fa3fddf00e658e6"
PROTOCOL_REV = "877c2d4c50e170575f8b8e7fbf7b8fa89b1dc157"
HEADER_SHA256 = "bd2fa78d45353725952d7f9bd1fec17e3e19e4721af95f961d4d6b9285a1ffeb"
LIMINE_URL = f"https://github.com/Limine-Bootloader/Limine/releases/download/{LIMINE_VERSION}/limine-binary.tar.gz"
HEADER_URL = f"https://raw.githubusercontent.com/limine-bootloader/limine-protocol/{PROTOCOL_REV}/include/limine.h"


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)
def pinned_file(path: Path, url: str, expected: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return path
    if path.exists():
        raise RuntimeError(f"cached dependency digest mismatch: {path}")
    with urlopen(url, timeout=40) as response:
        data = response.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise RuntimeError(f"dependency too large: {url}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise RuntimeError(f"pinned dependency checksum mismatch: {url}: {digest}")
    path.write_bytes(data)
    return path


def get_limine(cache: Path) -> tuple[Path, Path]:
    archive = pinned_file(cache / "limine-v12.11.1.tar.gz", LIMINE_URL, LIMINE_TAR_SHA256)
    header = pinned_file(cache / "limine.h", HEADER_URL, HEADER_SHA256)
    dist = cache / "limine-v12.11.1"
    tool = dist / "limine-binary" / "limine"
    if not tool.is_file():
        dist.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(dist, filter="data")
        run("make", "-C", dist / "limine-binary")
    return dist / "limine-binary", header
def build(source: Path, out: Path, cache: Path, work_root: Path, test_exit: bool,
          memory_probe: bool = False, memory_probe_badmap: bool = False,
          video_console: bool = False, video_test: bool = False) -> None:
    dist, header = get_limine(cache)
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="htmlk-boot-", dir=work_root) as temp:
        build_dir = Path(temp)
        generated = build_dir / "kernel.c"
        generated_obj = build_dir / "html_kernel.o"
        entry_obj = build_dir / "entry.o"
        kernel = build_dir / "kernel.elf"
        iso_root = build_dir / "iso_root"
        run(sys.executable, ROOT / "compiler/htmlk.py", source.resolve(), "--out", generated)
        flags = ["-std=c11", "-O2", "-ffreestanding", "-fno-builtin",
                 "-fno-stack-protector", "-fno-pie", "-fno-pic", "-fno-common",
                 "-mno-red-zone", "-mcmodel=kernel", "-mgeneral-regs-only",
                 "-fcf-protection=none", "-Wall", "-Wextra", "-Werror"]
        define = ["-DHTMLK_QEMU_TEST_EXIT"] if test_exit else []
        if memory_probe_badmap and not memory_probe:
            raise ValueError("bad-map injection requires an explicit M3 memory probe")
        if video_test and not video_console:
            raise ValueError("framebuffer pixel oracle requires --video-console")
        if video_console:
            define.append("-DHTMLK_FB_CONSOLE")
        if video_test:
            define.append("-DHTMLK_FB_TEST")
        if memory_probe:
            define.append("-DHTMLK_M3_MEMORY_PROBE")
        if memory_probe_badmap:
            define.append("-DHTMLK_M3_BAD_MAP_TEST")
        run("gcc", *flags, *define, "-c", generated, "-o", generated_obj)
        run("gcc", *flags, *define, "-I", header.parent, "-c",
            ROOT / "boot/kernel_entry.c", "-o", entry_obj)
        extra_objects: list[Path] = []
        if memory_probe or video_console:
            sources = (["page_pool", "memory_probe"] if memory_probe else [])
            if video_console:
                sources.append("console_fb")
            for source_name in sources:
                obj = build_dir / (source_name + ".o")
                run("gcc", *flags, *define, "-I", header.parent, "-I", ROOT / "boot",
                    "-c", ROOT / "boot" / (source_name + ".c"), "-o", obj)
                extra_objects.append(obj)
        run("gcc", "-nostdlib", "-no-pie", "-Wl,--build-id=none",
            "-Wl,-z,max-page-size=0x1000", "-Wl,-T," + str(ROOT / "boot/linker.ld"),
            "-o", kernel, entry_obj, generated_obj, *extra_objects)
        run("readelf", "-h", kernel)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kernel, out.with_suffix(".elf"))
        boot = iso_root / "boot"
        limine = boot / "limine"
        limine.mkdir(parents=True)
        (iso_root / "EFI/BOOT").mkdir(parents=True)
        shutil.copy2(kernel, boot / "kernel")
        shutil.copy2(ROOT / "boot/limine.conf", limine / "limine.conf")
        for name in ("limine-bios.sys", "limine-bios-cd.bin", "limine-uefi-cd.bin"):
            shutil.copy2(dist / name, limine / name)
        shutil.copy2(dist / "BOOTX64.EFI", iso_root / "EFI/BOOT/BOOTX64.EFI")
        out.parent.mkdir(parents=True, exist_ok=True)
        run("xorriso", "-as", "mkisofs", "-R", "-r", "-J",
            "-b", "boot/limine/limine-bios-cd.bin", "-no-emul-boot",
            "-boot-load-size", "4", "-boot-info-table",
            "--efi-boot", "boot/limine/limine-uefi-cd.bin",
            "-efi-boot-part", "--efi-boot-image", "--protective-msdos-label",
            "-o", out.resolve(), iso_root)
        run(dist / "limine", "bios-install", out.resolve())
    print(f"ISO: {out} SHA256={hashlib.sha256(out.read_bytes()).hexdigest()}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "examples/kernel.html")
    parser.add_argument("--out", type=Path, default=ROOT / "build/html-kernel.iso")
    parser.add_argument("--cache-dir", type=Path, default=Path(os.getenv(
        "HTMLK_CACHE_DIR", str(ROOT / "build/.cache"))))
    parser.add_argument("--work-dir", type=Path, default=Path(os.getenv(
        "HTMLK_WORK_DIR", str(ROOT / "build"))))
    parser.add_argument("--test-exit", action="store_true",
                        help="Enable QEMU debug-exit port for deterministic CI assertion")
    parser.add_argument("--memory-probe", action="store_true",
                        help="Opt-in M3 Limine map + 16-page HHDM allocator test")
    parser.add_argument("--memory-probe-badmap", action="store_true",
                        help="M3 negative test only; corrupt a local map copy")
    parser.add_argument("--video-console", action="store_true",
                        help="Opt-in M3 native Limine RGB framebuffer text output")
    parser.add_argument("--video-test", action="store_true",
                        help="QEMU-only framebuffer on-device pixel verification")
    a = parser.parse_args()
    if a.video_test and not a.video_console:
        parser.error("--video-test requires --video-console")
    if a.memory_probe_badmap and not a.memory_probe:
        parser.error("--memory-probe-badmap requires --memory-probe")
    build(a.source, a.out, a.cache_dir, a.work_dir, a.test_exit,
          a.memory_probe, a.memory_probe_badmap,
          a.video_console, a.video_test)


if __name__ == "__main__":
    main()
