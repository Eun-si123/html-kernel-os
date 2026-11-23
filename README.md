# HTML Kernel OS

**An experiment to express native kernel behavior with HTML-like syntax.**

HTML is normally a document language. This repository explores a dedicated compiler that interprets a restricted set of HTML-style elements as *systems-programming instructions*. The long-term goal is a self-booting OS whose kernel logic is written in that language.

> **Current status: VERIFIED BOOTABLE DEMO KERNEL (QEMU BIOS + browser), NOT A USABLE OS.** A restricted HTML dialect compiles to freestanding x86-64 C; Limine starts the generated kernel. Real QEMU source-mutation/negative controls passed locally and on GitHub CI. The same boot ISO was independently booted in Chromium using the v64 WebAssembly x86-64 emulator: [try the browser demo](https://eun-si123.github.io/html-kernel-os/play.html). UEFI, mobile-browser compatibility and physical hardware remain unverified. No general-purpose memory manager, filesystem, scheduler or general hardware drivers; M3 currently has a limited verified physical-page probe.

## Agent and contributor entry points

AI agents and external contributors: start at **[AGENTS.md](AGENTS.md)**, then follow **[CODEMAP.md](CODEMAP.md)** and the [documentation hub](docs/README.md). The repository uses TeamForge/BetterNet-style instructions for task ownership, public-safe commit attribution, current status, durable memory and advisory [feature-to-regression mapping](agent-evals/README.md). The instructions do not start a background agent or imply automatic deployment.

Read [actual implementation status](docs/STATUS.md) and [evidence criteria](docs/VALIDATION.md) before claiming native boot support. See [current decisions](docs/DECISIONS.md) for confirmed versus proposed scope. The [founder interview record](docs/INTERVIEW_DECISIONS.md) captures Q1–Q20: the reusable HTML-like language and usable Linux-based prototype remain design goals; a **minimal independent kernel and browser boot experiment** now run, but not a full OS. The [implementation plan](docs/IMPLEMENTATION_PLAN.md) prioritizes actual QEMU boot proof and a reusable language core.

## Roadmap for people and agents / 개발 계획

Start with the **[M0–M6 milestone roadmap](docs/ROADMAP.md)**: M1 actual QEMU BIOS boot is **verified by local tests and GitHub CI**; M2 core language programming features have native QEMU/Linux evidence; M3 memory and fault handling are NEXT. Read the [language design / Python ease comparison](docs/LANGUAGE_DESIGN.md), [C++/Rust-class performance goal and measurement contract](docs/PERFORMANCE.md), and [risk/assumption register](docs/PROJECT_RISKS.md) before proposing syntax or hardware changes. Milestones are *not* dates or release promises; [STATUS](docs/STATUS.md) owns observed progress. Agents can open milestone-scoped Issues with [this shared task template](.github/ISSUE_TEMPLATE/roadmap-task.md).

## Try the working prototype

Requirements: Python 3.10+ and an x86-64 GCC cross/native compiler.

~~~bash
python3 -m unittest discover -s tests -v
python3 compiler/htmlk.py examples/kernel.html --out build/kernel.c
gcc -std=c11 -ffreestanding -fno-stack-protector -fno-pie \
  -Wall -Wextra -Werror -c build/kernel.c -o build/kernel.o
file build/kernel.o
~~~

Input:

~~~html
<kernel arch="x86_64">
  <onboot>
    <print>Hello from HTML Kernel!</print>
    <halt/>
  </onboot>
</kernel>
~~~

Generated C defines `kernel_main()`, writes to QEMU debugcon `0xE9` and COM1 serial, then halts. The [Limine boot build](scripts/build_boot.py) now links this function into a real **minimal bootable kernel**; it is not a general-purpose OS or proven portable across physical hardware. Python is needed only at build time, not by the running kernel.

## Test real M2 language features

The experimental language now supports **signed i32/i64 and unsigned u32/u64**, fixed-width wrapping arithmetic, defined integer division/remainder with divide-by-zero traps, zero-initialized fixed-size typed arrays with checked indexes, explicit conversions, unsigned bitwise/shift operations, bounded repeat and capped conditional `while` loops with `break`/`continue`, `if/else` and scoped typed functions (up to four parameters). The compiler's signed arithmetic avoids undefined C signed-overflow behavior. For example, [signed-bits-kernel.html](examples/signed-bits-kernel.html) prints the signed minimum values, safely wrapped results and loop-control output from an actual native kernel. The **same HTML source compiles to x86-64 kernel or an unprivileged Linux executable**. Neither functions nor ordinary source can directly access arbitrary hardware, I/O or memory; recursion and unbounded loops remain unavailable. **M2 is partially implemented, not a complete OS.**

To verify this locally with GCC, QEMU and xorriso, run:

~~~sh
python3 scripts/test_language_boot.py
python3 scripts/test_functions.py
python3 scripts/test_scoped_functions.py
python3 scripts/test_else.py
python3 scripts/test_u32.py
python3 scripts/test_signed_bits.py
python3 scripts/test_division.py
python3 scripts/test_division_oracle.py
python3 scripts/test_arrays.py
python3 scripts/test_m2_gate.py
python3 scripts/test_integer_oracle.py
python3 scripts/build_boot.py --source examples/math-kernel.html --out build/html-kernel-math.iso
python3 scripts/build_boot.py --source examples/functions-kernel.html --out build/html-kernel-functions.iso
python3 scripts/build_boot.py --source examples/scoped-functions-kernel.html --out build/html-kernel-scoped.iso
python3 scripts/build_boot.py --source examples/else-kernel.html --out build/html-kernel-else.iso
python3 scripts/build_boot.py --source examples/u32-kernel.html --out build/html-kernel-u32.iso
python3 scripts/build_boot.py --source examples/signed-bits-kernel.html --out build/html-kernel-signed.iso
python3 scripts/build_boot.py --source examples/division-kernel.html --out build/html-kernel-division.iso
python3 scripts/build_boot.py --source examples/array-kernel.html --out build/html-kernel-array.iso
python3 scripts/build_boot.py --source examples/m2-exercises-kernel.html --out build/html-kernel-m2-exercises.iso
~~~

The [language contract](docs/M2_LANGUAGE_CONTRACT.md) documents syntax, safety bounds and unsupported expressions. The public [web boot lab](https://eun-si123.github.io/html-kernel-os/play.html) provides real x86-64 kernel examples for arithmetic, functions, scoped bodies, `if/else` branches u32/u64 native types and signed/bitwise/loop control (each ISO is generated and validated independently).

## Linux userspace target (P2: same language, no privileged I/O)

The same HTML-shaped source now compiles to a **real unprivileged x86-64 Linux executable**, reusing the exact parser, expression semantics, variables, conditions and loop constructs used by the independent kernel. Linux uses the C standard output library; kernel mode uses debugcon and COM1. This is **not** a Linux distribution, a graphical desktop, or legacy application support.

~~~sh
python3 compiler/htmlk.py examples/math-kernel.html --target linux --out build/math-linux.c
gcc -std=c11 -O2 -Wall -Wextra -Werror build/math-linux.c -o build/math-linux
./build/math-linux
python3 scripts/test_linux.py
~~~

The native Linux executable prints the same 14, 16, 18, condition PASS and u64 wraparound value as the QEMU kernel demo. A final halt tag becomes **normal process exit**, not a privileged CPU halt instruction.

## Project layout

- compiler/language.py — strict HTML AST and typed expression validation
- compiler/htmlk.py — shared kernel/Linux native C code generator
- examples/kernel.html — minimal source example
- tests/ — parser/codegen unit tests
- site/ — deployed [project-scoped GitHub Pages site](https://eun-si123.github.io/html-kernel-os/) and browser boot lab
- docs/ARCHITECTURE.md — design choices and explicit limitations
- .github/workflows/ci.yml — automated prototype checks

## Roadmap

1. [x] Define a minimal source grammar and compile to freestanding C.
2. [x] Add tests for good/bad inputs and object compilation.
3. [x] Integrate a pinned x86-64 Limine boot protocol, verify real QEMU boot including source changes and negative tests in CI.
4. [ ] Add freestanding memory primitives and interrupt/exception handling.
5. [ ] Define systems semantics for tasks, drivers, I/O and more expressive HTML constructs.
6. [ ] Evaluate whether native codegen (or LLVM IR) is more sustainable than C-as-IR.

## Website / GitHub Pages

The user requested a **project-specific static GitHub Pages browser boot lab**, separate from the existing personal github.io homepage. The Pages workflow is deployed: visit https://eun-si123.github.io/html-kernel-os/play.html to boot the generated ISO in a WebAssembly x86-64 emulator (verified in one Chromium browser). The host is static: JavaScript runs the emulator on the visitor's machine, not on GitHub's servers. The browser boot was independently verified via Playwright with exact COM1 output; mobile and other browser engines remain untested. The workflow builds and uploads the ISO and checksum-pinned v64 x86-64 WebAssembly emulator assets; the pinned emulator's ~4 MB of browser binaries are versioned in `site/vendor/` so GitHub Actions does not depend on third-party downloads. Browser emulator license in `site/v86-LICENSE.txt`.

Local preview:

~~~bash
python3 -m http.server 8000 --directory site
~~~

Then open http://127.0.0.1:8000 in your browser.

## Scope and naming

"HTML kernel" is shorthand for a **new programming language with HTML-like syntax**. This is not standard HTML, not a browser engine, and not an existing production OS. A source language written in angle brackets still needs a compiler and a CPU-executable entry point.

## License

**No license has been selected yet.** Public visibility does not grant open-source reuse rights by itself; a license decision should be made before encouraging outside contributions.

## M3 memory bootstrap experiment (separate from normal boot)

An opt-in Limine memory-map/HHDM probe now selects exactly 16 usable, 4KiB-aligned physical pages, performs actual RAM readback through HHDM, and checks exhaustion. The ordinary HTML-derived kernel image is unchanged. Run `python3 scripts/test_m3_memory.py` to check the freestanding C page-pool logic with GCC UBSan and run positive/negative real BIOS QEMU boots, or build a manually bootable test ISO with `python3 scripts/build_boot.py --memory-probe --out build/html-kernel-m3-memory.iso`. This is **only the initial M3 physical memory slice**: no virtual page mapping, IRQ/TSS support, real PC verification or user-program isolation (a separate opt-in fail-stop CPU IDT now exists). Full design and limitations: [M3 memory bootstrap](docs/M3_MEMORY_BOOTSTRAP.md).

## Native screen output experiment (M3, not a graphical desktop)

A new opt-in **real RGB framebuffer console** makes the actual booted x86-64 kernel write text pixels into its Limine framebuffer. Existing `<print>` source writes to the QEMU debugcon and COM1 **and** to the real monitor when enabled. Build a standalone ISO with:

```sh
python3 scripts/build_boot.py --source examples/framebuffer-kernel.html --video-console --out build/html-kernel-video.iso
python3 scripts/test_video_console.py
python3 scripts/test_video_screen.py
```

The original five-by-seven bitmap renderer is implemented in `boot/console_fb.c`, with safe mode validation, bounded dimensions, line wrapping and a dark display palette. GCC/QEMU's x86-64 ISA is pinned explicitly; previously an unsupported BMI2 `SHLX` instruction caused a real QEMU #UD/triple fault before screen output, now fixed with `-march=x86-64 -mno-bmi2`. Tests distinguish actual Limine pixel readback from serial text, and a separate QEMU VGA screenshot oracle checks visible pixels. This is an **opt-in native ISO and GitHub Actions artifact**, not yet wired to the public browser Boot Lab. There is no keyboard interaction, Unicode font, window manager, general graphics driver or verified physical PC display. See [M3 framebuffer contract](docs/M3_FRAMEBUFFER_CONSOLE.md).

## M3 native CPU exception IDT (fail-stop prototype)

The new opt-in `--exception-idt` flag installs a 256-descriptor x86-64 IDT with ring-0 CPU exception vectors 0–31, then proceeds into the **same source-generated HTML kernel**. Actual QEMU tests generate real `#DE` divide faults, `#UD` invalid instructions, `#GP` protection faults and `#PF` page faults; instead of silently triple-faulting/rebooting, the kernel logs vector number, RIP, error code and CR2 where relevant, then halts. This is **fault detection and fail-stop only**, not error recovery, page table isolation or keyboard/IRQ support. Tests independently verify native gate ABI/descriptor layout and combined operation with previous M3 memory/framebuffer features:

```sh
python3 scripts/test_exception_idt.py
python3 scripts/build_boot.py --exception-idt --out build/html-kernel-m3-exceptions.iso
```

See [M3_EXCEPTION_IDT.md](docs/M3_EXCEPTION_IDT.md). Real hardware/UEFI and browser testing for this new feature are NOT RUN; the public Boot Lab remains on its existing seven older demos.

## M3 isolated virtual mapping proof (not a general VM manager)

The opt-in `--paging-probe` builds **a private page-table root**, copies the active Limine PML4 without changing it, and maps one 4KiB USABLE physical frame to a fixed supervisor-only virtual alias. In BIOS QEMU the kernel verifies alias read/write, clears the PTE, invalidates the TLB and restores the original CR3 before source-generated HTML executes. A separate real CPU post-unmap access must raise #PF; the opt-in `--exception-idt` records CR2 and exits the test kernel with non-success 45. This is an **M3 experimental mapping slice**, not general-purpose virtual allocation, page-fault recovery, process isolation, TSS/IST or physical-PC verification.

```sh
python3 scripts/test_paging_probe.py
python3 scripts/build_boot.py --exception-idt --paging-probe --out build/html-kernel-m3-paging.iso
```

See [M3_PRIVATE_PAGING.md](docs/M3_PRIVATE_PAGING.md). The existing public browser Boot Lab is unchanged.
