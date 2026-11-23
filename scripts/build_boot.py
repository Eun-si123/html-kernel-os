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
          video_console: bool = False, video_test: bool = False,
          exception_idt: bool = False, fault_test: str | None = None,
          paging_probe: bool = False, paging_fault_test: bool = False,
          paging_recover_test: bool = False, owned_frame_test: bool = False,
          tss_ist: bool = False, double_fault_test: bool = False,
          multi_page_test: bool = False, multi_page_fault_test: bool = False,
          task_probe: bool = False, task_negative_test: bool = False,
          timer_probe: bool = False, timer_mask_test: bool = False,
          preempt_probe: bool = False, preempt_timer_mask: bool = False,
          preempt_bad_frame: bool = False) -> None:
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
        # Deterministic guest ISA: hosted GCC may target BMI2 (SHLX),
        # but baseline QEMU qemu64 deliberately lacks that extension.
        flags = ["-std=c11", "-O2", "-march=x86-64", "-mtune=generic",
                 "-mno-bmi2", "-ffreestanding", "-fno-builtin",
                 "-fno-stack-protector", "-fno-pie", "-fno-pic", "-fno-common",
                 "-mno-red-zone", "-mcmodel=kernel", "-mgeneral-regs-only",
                 "-fcf-protection=none", "-Wall", "-Wextra", "-Werror"]
        define = ["-DHTMLK_QEMU_TEST_EXIT"] if test_exit else []
        if preempt_probe and (not exception_idt or task_probe or timer_probe or
                              paging_probe or memory_probe or video_console or
                              tss_ist or fault_test is not None):
            raise ValueError("M4 x2APIC preemption requires only the IDT (no other probes)")
        if preempt_bad_frame and not (preempt_probe and test_exit):
            raise ValueError("M4 bad-frame negative requires preempt-probe and test-exit")
        if preempt_bad_frame:
            define.append("-DHTMLK_M4_PREEMPT_BAD_FRAME_TEST")
        if preempt_timer_mask and not (preempt_probe and test_exit):
            raise ValueError("M4 x2APIC masked negative requires preempt-probe and test-exit")
        if preempt_probe:
            define.append("-DHTMLK_M4_X2APIC_PREEMPT")
        if preempt_timer_mask:
            define.append("-DHTMLK_M4_PREEMPT_TIMER_MASK_TEST")
        if timer_probe and not (exception_idt and task_probe):
            raise ValueError("M4 PIT timer requires --exception-idt and --task-probe")
        if timer_mask_test and not (timer_probe and test_exit):
            raise ValueError("M4 timer mask negative requires --timer-probe --test-exit")
        if timer_probe:
            define.append("-DHTMLK_M4_TIMER_PROBE")
        if timer_mask_test:
            define.append("-DHTMLK_M4_TIMER_MASK_TEST")
        if task_negative_test and not task_probe:
            raise ValueError("M4 negative task oracle needs task probe")
        if task_probe:
            define.append("-DHTMLK_M4_TASK_PROBE")
        if task_negative_test:
            define.append("-DHTMLK_M4_TASK_NEGATIVE_TEST")
        if multi_page_test and not paging_probe:
            raise ValueError("multi-page test requires paging probe")
        if multi_page_fault_test and not (multi_page_test and exception_idt and test_exit):
            raise ValueError("multi-page fault test requires mapping, IDT and test-exit")
        if multi_page_fault_test and paging_recover_test:
            raise ValueError("multi-page revocation and recovery tests are exclusive")
        if multi_page_test:
            define.append("-DHTMLK_M3_MULTI_PAGE_TEST")
        if multi_page_fault_test:
            define.append("-DHTMLK_M3_MULTI_PAGE_FAULT_TEST")
        if tss_ist and not exception_idt:
            raise ValueError("TSS/IST needs an installed exception IDT")
        if double_fault_test and not (tss_ist and exception_idt and test_exit):
            raise ValueError("real #DF injection requires TSS/IST, IDT and test-exit")
        if double_fault_test and fault_test is not None:
            raise ValueError("double-fault and other CPU fault injections are exclusive")
        if tss_ist:
            define.append("-DHTMLK_M3_IST_STACK")
        if double_fault_test:
            define.append("-DHTMLK_M3_DOUBLE_FAULT_TEST")
        if fault_test is not None and not exception_idt:
            raise ValueError("CPU fault injection requires the opt-in exception IDT")
        if paging_fault_test and not (paging_probe and exception_idt):
            raise ValueError("paging fault injection needs paging probe and exception IDT")
        if paging_recover_test and not (paging_probe and exception_idt):
            raise ValueError("paging recovery needs paging probe and exception IDT")
        if paging_fault_test and paging_recover_test:
            raise ValueError("paging fail-stop and recovery test modes are mutually exclusive")
        if owned_frame_test and not paging_probe:
            raise ValueError("owned frame test needs paging probe")
        if paging_recover_test:
            define.append("-DHTMLK_M3_PAGING_RECOVER_TEST")
        if owned_frame_test:
            define.append("-DHTMLK_M3_OWNED_FRAME_TEST")
        if paging_probe:
            define.append("-DHTMLK_M3_PAGING_PROBE")
        if paging_fault_test:
            define.append("-DHTMLK_M3_PAGING_UNMAP_FAULT_TEST")
        if exception_idt:
            define.append("-DHTMLK_M3_EXCEPTION_IDT")
        faults = {"ud": "UD", "page": "PF", "divide": "DE", "general": "GP"}
        if fault_test is not None:
            if fault_test not in faults:
                raise ValueError(f"unsupported CPU fault test {fault_test!r}")
            define.append("-DHTMLK_M3_FAULT_" + faults[fault_test])
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
        if memory_probe or video_console or exception_idt or paging_probe or tss_ist or task_probe or preempt_probe:
            sources = (["page_pool"] if (memory_probe or paging_probe) else [])
            if memory_probe:
                sources.append("memory_probe")
            if task_probe:
                sources.extend(("task_model", "task_runtime"))
            if timer_probe:
                sources.append("timer_irq")
            if preempt_probe:
                sources.append("preempt_x2apic")
            if paging_probe:
                sources.extend(("frame_owner", "paging_tables", "paging_probe"))
            if exception_idt:
                sources.append("exception_idt")
            if tss_ist:
                sources.append("tss_ist")
            if video_console:
                sources.append("console_fb")
            for source_name in sources:
                obj = build_dir / (source_name + ".o")
                run("gcc", *flags, *define, "-I", header.parent, "-I", ROOT / "boot",
                    "-c", ROOT / "boot" / (source_name + ".c"), "-o", obj)
                extra_objects.append(obj)
            if task_probe:
                obj = build_dir / "task_switch.o"
                run("gcc", "-c", "-m64", "-fno-pie", "-fno-pic",
                    ROOT / "boot/task_switch.S", "-o", obj)
                extra_objects.append(obj)
            if preempt_probe:
                obj = build_dir / "preempt_switch.o"
                run("gcc", "-c", "-m64", "-fno-pie", "-fno-pic",
                    ROOT / "boot/preempt_switch.S", "-o", obj)
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
    parser.add_argument("--exception-idt", action="store_true",
                        help="Opt-in M3 32-vector x86-64 fail-stop exception handling")
    parser.add_argument("--fault-test", choices=("ud", "page", "divide", "general"),
                        help="Test-only genuine CPU fault; requires --exception-idt")
    parser.add_argument("--paging-probe", action="store_true",
                        help="Opt-in M3 private 4KiB CR3 mapping, alias and unmap probe")
    parser.add_argument("--paging-fault-test", action="store_true",
                        help="Real post-unmap #PF; needs --paging-probe and --exception-idt")
    parser.add_argument("--paging-recover-test", action="store_true",
                        help="One-shot lazy #PF recovery; requires paging probe and IDT")
    parser.add_argument("--owned-frame-test", action="store_true",
                        help="QEMU negative frame ownership/reclaim/exhaustion oracle")
    parser.add_argument("--tss-ist", action="store_true",
                        help="Opt-in x86-64 GDT/TSS IST1 #DF and IST2 #PF stacks; needs IDT")
    parser.add_argument("--double-fault-test", action="store_true",
                        help="Test-only corrupted IST2 -> real #DF; requires IDT/TSS/test-exit")
    parser.add_argument("--multi-page-test", action="store_true",
                        help="Opt-in M3 three extra private 4KiB aliases and reclaimed frames")
    parser.add_argument("--multi-page-fault-test", action="store_true",
                        help="Real #PF after reclaiming additional page; needs IDT and test-exit")
    parser.add_argument("--task-probe", action="store_true",
                        help="Opt-in M4-A real ring-0 cooperative task contexts")
    parser.add_argument("--task-negative-test", action="store_true",
                        help="Reject unsafe task states in native QEMU; needs task probe")
    parser.add_argument("--timer-probe", action="store_true",
                        help="Opt-in real QEMU PIT/PIC IRQ0 task progress, needs IDT and tasks")
    parser.add_argument("--timer-mask-test", action="store_true",
                        help="Intentionally mask IRQ0 for bounded QEMU timeout negative oracle")
    parser.add_argument("--preempt-probe", action="store_true",
                        help="Opt-in M4-B2 actual x2APIC IRQ driven ring-0 preemption")
    parser.add_argument("--preempt-timer-mask", action="store_true",
                        help="M4-B2 QEMU negative: mask x2APIC timer interrupt")
    parser.add_argument("--preempt-bad-frame", action="store_true",
                        help="M4-B2 QEMU negative: reject intentionally misaligned task context")
    a = parser.parse_args()
    if a.preempt_probe and (not a.exception_idt or a.task_probe or a.timer_probe or
                            a.paging_probe or a.memory_probe or a.video_console or
                            a.tss_ist or a.fault_test is not None):
        parser.error("--preempt-probe needs --exception-idt alone (no other probes)")
    if a.preempt_bad_frame and not (a.preempt_probe and a.test_exit):
        parser.error("--preempt-bad-frame needs --preempt-probe --test-exit")
    if a.preempt_timer_mask and not (a.preempt_probe and a.test_exit):
        parser.error("--preempt-timer-mask needs --preempt-probe --test-exit")
    if a.timer_probe and not (a.exception_idt and a.task_probe):
        parser.error("--timer-probe requires --exception-idt and --task-probe")
    if a.timer_mask_test and not (a.timer_probe and a.test_exit):
        parser.error("--timer-mask-test requires --timer-probe and --test-exit")
    if a.task_negative_test and not a.task_probe:
        parser.error("--task-negative-test requires --task-probe")
    if a.multi_page_test and not a.paging_probe:
        parser.error("--multi-page-test requires --paging-probe")
    if a.multi_page_fault_test and not (a.multi_page_test and a.exception_idt and a.test_exit):
        parser.error("--multi-page-fault-test requires --multi-page-test, --exception-idt and --test-exit")
    if a.multi_page_fault_test and a.paging_recover_test:
        parser.error("--multi-page-fault-test conflicts with --paging-recover-test")
    if a.tss_ist and not a.exception_idt:
        parser.error("--tss-ist requires --exception-idt")
    if a.double_fault_test and not (a.tss_ist and a.exception_idt and a.test_exit):
        parser.error("--double-fault-test requires --tss-ist, --exception-idt and --test-exit")
    if a.double_fault_test and a.fault_test is not None:
        parser.error("--double-fault-test conflicts with --fault-test")
    if a.paging_recover_test and not (a.paging_probe and a.exception_idt):
        parser.error("--paging-recover-test requires --paging-probe and --exception-idt")
    if a.paging_fault_test and a.paging_recover_test:
        parser.error("--paging-fault-test and --paging-recover-test are mutually exclusive")
    if a.owned_frame_test and not a.paging_probe:
        parser.error("--owned-frame-test requires --paging-probe")
    if a.paging_fault_test and not (a.paging_probe and a.exception_idt):
        parser.error("--paging-fault-test requires --paging-probe and --exception-idt")
    if a.fault_test is not None and not a.exception_idt:
        parser.error("--fault-test requires --exception-idt")
    if a.video_test and not a.video_console:
        parser.error("--video-test requires --video-console")
    if a.memory_probe_badmap and not a.memory_probe:
        parser.error("--memory-probe-badmap requires --memory-probe")
    build(a.source, a.out, a.cache_dir, a.work_dir, a.test_exit,
          a.memory_probe, a.memory_probe_badmap,
          a.video_console, a.video_test, a.exception_idt, a.fault_test,
          a.paging_probe, a.paging_fault_test,
          a.paging_recover_test, a.owned_frame_test,
          a.tss_ist, a.double_fault_test,
          a.multi_page_test, a.multi_page_fault_test,
          a.task_probe, a.task_negative_test,
          a.timer_probe, a.timer_mask_test,
          a.preempt_probe, a.preempt_timer_mask, a.preempt_bad_frame)


if __name__ == "__main__":
    main()
