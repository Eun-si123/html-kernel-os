# M5-F1 — HTML-like language compiles to a *separate* native Ring 3 program

**Status:** feature-branch mini-PC native QEMU BIOS proof PASS; exact PR-head CI and merge must be confirmed separately. This is a constrained user target, not an ELF loader, safe arbitrary-code sandbox, HTML browser runtime or complete M5/M6 OS.

## Quickstart / reproduce

On Ubuntu with Python 3, GCC/binutils, QEMU, xorriso and the pinned Limine build cache:

```sh
# One command for the actual COM1 interactive shell (automatically opts in
# to guarded Ring3 and x2APIC timeout; no host disk or network is attached):
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-hello.html

# Native independently compiled x86-64 user application, not kernel source
python3 scripts/build_html_user_image.py --source examples/user-programs/html-hello.html --out build/html-hello.hke
python3 compiler/htmlk.py examples/user-programs/html-hello.html --target user --out build/html-hello-user.c
# Generate separate native boot ISO with the HTML user app in /apps/hello.hke
python3 scripts/build_boot.py --exception-idt --tss-ist --romfs-run-console --user-fault-recover --user-timeout --user-app-html examples/user-programs/html-hello.html --out build/m5-html-user.iso
# Automated actual BIOS QEMU UART run/exit and independent source mutations
python3 scripts/test_m5_html_user.py
python3 -m unittest tests.test_html_user_target -v
```

To interact with the ISO manually, run QEMU with `-M q35 -cpu qemu64,+x2apic -smp 1 -m 256M -serial stdio`, the same BIOS/COM1/debugcon options as `scripts/run_m5_console.py`, and enter `run /apps/hello.hke`, `help`, `exit`.

## Shared semantics, isolated user-mode backend

The **existing** `compiler/language.py` strict HTML parser, typed expression checker and bounded M2 function/array/loop code generators are reused. `compiler/htmlk.py --target user` adds no separate parser or user-controlled raw memory API. This is a build-time source compilation mode (HTML-like language → freestanding C → GCC x86-64 code → relocation-free flat executable). The guest sees only the native HKEX bytes, never executes HTML markup or a Python interpreter.

The intentionally bounded input contract is `<kernel arch="x86_64"><onboot>...<print value="unsigned_expression"/><halt/></onboot></kernel>` (ordinary M2 numeric operations, typed variables, conditions, bounded loops, pure functions, checked arrays). There must be **exactly one final top-level numeric print** before halt. Source string `<print>hello</print>`, multiple/dynamic nested reports, signed report types, invalid tags and malformed expressions fail at build time, **before an ISO is created**. No `<app>` root syntax yet; the shared `<kernel>` wrapper reflects the existing language grammar rather than changing it for this slice.

The `user` backend never emits privileged OUTB, CLI or HLT for normal user-mode execution. Its generated code first writes and reads a private CPL3 stack marker, calls `INT 0x80` operation 0 to prove its register-only stack ABI, uses operation 2 to report a single unsigned **0..9999** result in RDI, then calls operation 1 to exit. Values outside the report range become controlled per-program syscall failures **only** in the M5-E1 opt-in recovered shell; standalone legacy M5-C1 retains its prior fail-stop behavior.

`scripts/build_html_user_image.py` assembles a tiny position-relative entry shim, compiles generated C without hosted libraries, links with `scripts/user_program.ld` starting at virtual offset zero, **requires only one allocated `.text` section, no relocations and at most 4064 executable bytes**, then reuses the existing M5-C1 `pack()` HKEX header/checksum. The shell preflights the exact ROMFS bytes and the guest rechecks them before copying into private CPL3 read-only code plus writable stack pages, using the existing owned-frame path. FNV-1a is byte corruption detection, **not code authenticity**, and programs remain **trusted build-time sources**.

## Native evidence and separate regressions

- Three independent real QEMU q35 BIOS boots: user HTML numeric expression computes `2026`, actual COM1 `run` twice, fresh Ring3 page sets and 6-frame reclaim after each exit, `help`, and a real non-yielding separate assembly app retired by x2APIC timer in the same boot. Exact success guest exit 33 followed by HTML-generated kernel text.
- Change only HTML **user** source `1046→1045` → different HKEX/ISO → actual Ring3 UART reports `2027` instead of `2026`.
- Change only HTML **kernel** source → different ISO and real output while user program continues to execute.
- Negative unit/compiler coverage: strings, duplicate/nested prints, signed reports, malformed typed source, symlinked or oversized source, invalid CLI flag combinations, no output artifact on failure; determinism/length/header checksum.
- `tests/test_html_user_target.py` covers parser/target and host GCC image properties; `scripts/test_m5_html_user.py` is the actual CPU/ROMFS/COM1 test. Existing standalone M4/M5 regression tests run independently.

## Explicitly open

Only one fixed-width, register-only numeric report is currently supported, with a maximum 4KiB user code page and one user stack page. No text printing or user pointers/copyin, arbitrary ELF/DLL loading, dynamically writable files, I/O privilege, FS/GS/FPU/SMP support, calibrated timer, UEFI/real device evidence, or general untrusted code execution. The native browser Boot Lab uses a **different M1 ISO** and was not modified in this slice. Further HTML usability and full M5-E3/F gates remain open.
