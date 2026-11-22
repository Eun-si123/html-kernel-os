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
3. Output sends bytes to x86 I/O port 0xE9. This is **QEMU debugcon**, not VGA, a serial interface, or a real graphics driver.
4. The pipeline compiles only an object file. It does **not** generate an ELF kernel linked for booting or a bootable ISO.

## Boundaries

- HTML is being used as **syntax**, not as the web platform. The meaning of each tag is custom.
- Python runs only at build time; the generated machine code does not depend on Python or JavaScript.
- C currently acts as a portable intermediate representation. The objective is not to claim that C has disappeared from the build toolchain.
- No known boot protocol or linker layout is assumed to work until tested in QEMU.
- Native x86 instructions do not automatically make the result safe or portable to real machines.

## Risks and engineering decisions

- A multi-purpose HTML renderer is **not** needed for compiling the source.
- Freestanding compiler output is not itself a functional kernel; boot handoff, privilege state, interrupt state, and runtime support must be designed.
- debugcon is a development-only output channel. Standard device support needs additional code.
- Compiler validation must reject unsupported constructs predictably.
- Add reproducible QEMU boot tests **before** claiming kernel execution.
- Reevaluate syntax ergonomics before expanding the grammar; do not introduce faux-HTML tags without a clear low-level semantic contract.

## Proposed next milestone: QEMU boot

- Pin a specific Limine release, with checksum/provenance.
- Add correct Limine request structures and a linker script targeting x86_64.
- Compile HTML-derived object together with a tiny handoff shim only where unavoidable.
- Build a bootable image and run QEMU using explicit machine type and debugcon redirection.
- Assert the exact debug output and a deterministic halt/exit condition in CI.
- Label success only as "bootable demo kernel", not "operating system complete".
