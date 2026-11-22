# Architecture / evidence ledger

## Goal

Write kernel *logic* in a constrained HTML-like language. Translate it ahead of time to a freestanding native target, and eventually boot that target without a browser or host OS.

## What exists now

1. The Python stdlib HTMLParser validates a deliberately tiny grammar:
   - exactly one outer kernel element with x86_64 architecture;
   - one onboot block;
   - one or more print nodes containing up to 4096 UTF-8 bytes each;
   - optional halt;
   - no scripts, nested elements inside print, unknown attributes, or arbitrary HTML.
2. Code generation emits freestanding C source with a kernel_main() function.
3. Generated code initializes and outputs to COM1 at 0x3f8 alongside QEMU debugcon port 0xE9. Both outputs were seen in local QEMU boot. This is not VGA/framebuffer or a general hardware driver.
4. The original M0 pipeline compiles an object; the new `scripts/build_boot.py` links that object to the tiny Limine protocol handoff (`boot/kernel_entry.c`) using `boot/linker.ld` and packs a hybrid BIOS/UEFI ISO. BIOS x86-64 QEMU boot PASS locally and in GitHub CI with source provenance and negative controls. Live browser emulation PASS in one Chromium/Playwright session; UEFI and real PC boot are NOT yet verified.

## Boundaries

- HTML is being used as **syntax**, not as the web platform. The meaning of each tag is custom.
- Python runs only at build time; the generated machine code does not depend on Python or JavaScript.
- C currently acts as a portable intermediate representation. The objective is not to claim that C has disappeared from the build toolchain.
- The pinned Limine protocol and linker layout are verified in BIOS QEMU, but not in UEFI or on physical hardware.
- Native x86 instructions do not automatically make the result safe or portable to real machines.

## Risks and engineering decisions

- A multi-purpose HTML renderer is **not** needed for compiling the source.
- Freestanding compiler output is not itself a functional kernel; boot handoff, privilege state, interrupt state, and runtime support must be designed.
- debugcon is a development-only output channel. Standard device support needs additional code.
- Compiler validation must reject unsupported constructs predictably.
- Run reproducible QEMU boot tests in CI on every relevant change; only claim the exact platform tested.
- Reevaluate syntax ergonomics before expanding the grammar; do not introduce faux-HTML tags without a clear low-level semantic contract.

## M1 boot integration (implemented and verified; evidence in STATUS)

- Pin a specific Limine release, with checksum/provenance.
- Add correct Limine request structures and a linker script targeting x86_64.
- Compile HTML-derived object together with a tiny handoff shim only where unavoidable.
- Build a bootable image and run QEMU using explicit machine type and debugcon redirection.
- Assert the exact debug output and a deterministic halt/exit condition in CI.
- Label success only as "bootable demo kernel", not "operating system complete".
