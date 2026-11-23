# HTML Kernel OS

**An experiment to express native kernel behavior with HTML-like syntax.**

HTML is normally a document language. This repository explores a dedicated compiler that interprets a restricted set of HTML-style elements as *systems-programming instructions*. The long-term goal is a self-booting OS whose kernel logic is written in that language.

> **Current status: VERIFIED BOOTABLE DEMO KERNEL (QEMU BIOS + browser), NOT A USABLE OS.** A restricted HTML dialect compiles to freestanding x86-64 C; Limine starts the generated kernel. Real QEMU source-mutation/negative controls passed locally and on GitHub CI. The same boot ISO was independently booted in Chromium using the v64 WebAssembly x86-64 emulator: [try the browser demo](https://eun-si123.github.io/html-kernel-os/play.html). UEFI, mobile-browser compatibility and physical hardware remain unverified. No general-purpose memory manager, writable/disk filesystem, production task scheduler or general hardware drivers; bounded opt-in M3/M4 experiments and M5 immutable ROMFS + real QEMU UART terminal now exist. **M4-C1/C2** prove native CPL3 entry, syscalls and sequential fault isolation; the later bounded **M4-D** opt-in experiment also proves true x2APIC preemption and survivor fault cleanup in QEMU. **M5-A/B/C1/D1** provide an embedded read-only filesystem, real UART command input and a restricted, build-time embedded CPL3 user program launched with `run`; this does not constitute a production process manager or general-purpose filesystem.

## Agent and contributor entry points

AI agents and external contributors: start at **[AGENTS.md](AGENTS.md)**, then follow **[CODEMAP.md](CODEMAP.md)** and the [documentation hub](docs/README.md). The repository uses TeamForge/BetterNet-style instructions for task ownership, public-safe commit attribution, current status, durable memory and advisory [feature-to-regression mapping](agent-evals/README.md). The instructions do not start a background agent or imply automatic deployment.

Read [actual implementation status](docs/STATUS.md) and [evidence criteria](docs/VALIDATION.md) before claiming native boot support. See [current decisions](docs/DECISIONS.md) for confirmed versus proposed scope. The [founder interview record](docs/INTERVIEW_DECISIONS.md) captures Q1–Q20: the reusable HTML-like language and usable Linux-based prototype remain design goals; a **minimal independent kernel and browser boot experiment** now run, but not a full OS. The [implementation plan](docs/IMPLEMENTATION_PLAN.md) prioritizes actual QEMU boot proof and a reusable language core.

## Roadmap for people and agents / 개발 계획

Start with the **[M0–M6 milestone roadmap](docs/ROADMAP.md)**: M1 actual QEMU BIOS boot is **verified by local tests and GitHub CI**; M2 core language programming features have native QEMU/Linux evidence; M3 bounded memory/fault proof is complete; the bounded M4-D real CPL3 timer-preemption/fault-survivor experiment is merged and native QEMU-tested, but generic process safety is still open. M5-A/B/C1/D1 opt-in ROMFS, live COM1 and separate user `run` proofs are also merged; the next safety phase is M5-C2 program crash containment ([Issue #73](https://github.com/Eun-si123/html-kernel-os/issues/73)). Read the [language design / Python ease comparison](docs/LANGUAGE_DESIGN.md), [C++/Rust-class performance goal and measurement contract](docs/PERFORMANCE.md), and [risk/assumption register](docs/PROJECT_RISKS.md) before proposing syntax or hardware changes. Milestones are *not* dates or release promises; [STATUS](docs/STATUS.md) owns observed progress. Agents can open milestone-scoped Issues with [this shared task template](.github/ISSUE_TEMPLATE/roadmap-task.md).

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

## Try the native M5-B command console (actual BIOS QEMU)

On Ubuntu with an interactive terminal, GCC, xorriso and x86-64 QEMU installed (no host disk or network is passed to the guest):

```sh
python3 scripts/run_m5_console.py
```

Enter `help`, `ls`, `cat /welcome.txt`, `cat /config/build.txt`, then `exit`. This command builds the native ISO with actual immutable ROMFS source bytes and starts a QEMU COM1 **serial-input** session. It is independent of the browser boot lab, and is **not** a general interactive OS: commands still run in the privileged kernel and no separate user program is loaded. See [M5-B full QEMU acceptance evidence](docs/M5_SERIAL_CONSOLE.md). Automated, noninteractive equivalent: `python3 scripts/test_m5_console.py`.

## Live QEMU console `run` command (M5-D1)

On an Ubuntu host with GCC, QEMU, xorriso and a real terminal, use the existing runner with one flag:

```sh
python3 scripts/run_m5_console.py --with-user-program
```

Type `ls`, `cat /welcome.txt`, `run /apps/hello.hke` (repeat it if you like), then `exit`. This is an **actual** guest COM1 serial command launching a separate native program in CPL3 from a read-only ROMFS image; it returns to the shell. Invalid paths, absent and invalid executable files are handled without killing the shell. The original `python3 scripts/run_m5_console.py` remains the simpler M5-B console by default. The trusted app is still embedded at build time: it is not an arbitrary external executable or an HTML-compiled user app. [Exact M5-D1 evidence and limits](docs/M5_INTERACTIVE_RUN.md).

## Return to the native shell after a real user CPU fault (M5-E1)

On an interactive Ubuntu/QEMU terminal, after the M5-D1 proof use:

```sh
python3 scripts/run_m5_console.py --with-user-program --recover-user-faults
```

Run `run /apps/fault-io.hke`, `run /apps/fault-pf.hke`, `run /apps/fault-ro.hke` or `run /apps/fault-ud.hke`: each must cause a **real Ring3 CPU exception**, reclaim its own user memory and return to the original UART command prompt. Then `run /apps/hello.hke` still runs normally. A valid user image that calls an unsupported `INT 0x80` ID or invalid argument now also fails **only that program** (`M5_ERR_USER_SYSCALL`), with the same console and next `run` still usable. This is a separate opt-in experiment, **not** a sandbox for untrusted binaries: an infinite loop is not yet interruptible here. See [M5-E1 exact QEMU evidence and restrictions](docs/M5_USER_FAULT_RECOVERY.md).

## Compile an HTML-like program into its own native Ring 3 app (M5-F1)

The **same HTML parser and typed expression compiler** used for the kernel and Linux targets can now also generate a bounded user-mode executable. Try [`examples/user-programs/html-hello.html`](examples/user-programs/html-hello.html), which calculates and reports `2026` using a typed function, variable and repeat loop:

```sh
# Direct interactive console on Ubuntu:
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-hello.html
# Or generate the native image and run automated QEMU evidence:
python3 scripts/build_html_user_image.py --source examples/user-programs/html-hello.html --out build/html-hello.hke
python3 scripts/build_boot.py --exception-idt --tss-ist --romfs-run-console --user-fault-recover --user-timeout --user-app-html examples/user-programs/html-hello.html --out build/m5-html-user.iso
python3 scripts/test_m5_html_user.py
```

In the real QEMU COM1 shell, `run /apps/hello.hke` executes **independent HTML-derived machine code in Ring 3**, prints its numeric result and returns to the prompt with user frames reclaimed. This is a trusted build-time ROMFS application with **one unsigned numeric report (0..9999)**; it is not an HTML web page, nor a text/graphics API or a general ELF loader. See [M5-F1 native end-to-end contract](docs/M5_HTML_USER_PROGRAM.md).

## Print a checked ASCII string from a real native HTML user app (M5-F2)

The same HTML source format can now also write one **printable ASCII literal** through a carefully validated Ring3-to-kernel syscall: the kernel permits at most 96 bytes entirely inside the user's read-only code page, checks all bytes first, then sends them to the genuine guest COM1 UART (not a browser simulation). Try:

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-message.html
# In QEMU: run /apps/hello.hke, then help or exit
python3 scripts/test_m5_html_user_text.py
```

A bad supervisor pointer, overflowing length, or terminal escape causes **that user program** to be terminated with `M5_ERR_USER_SYSCALL`; the live shell continues and can run a correct app again. This is build-time trusted ASCII, **not** arbitrary userspace pointer/string access, Unicode printing or general-purpose process security. The real QEMU + negative evidence is in [M5-F2 contract](docs/M5_HTML_USER_TEXT.md).

## Repeat HTML user output safely (M5-F3)

The same native HTML user target can now run bounded `<print>` statements in conditions and capped loops, instead of producing only one message per process. **Both compiler and kernel enforce a maximum of eight reports per program**; a forged ninth syscall terminates only that user task and leaves the real UART console alive. Reuse the same one-command runner:

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-multireport.html
# Native QEMU: run /apps/hello.hke; exit
python3 scripts/test_m5_html_multi_report.py
```

The example prints `tick` twice followed by `2026`; string bytes are still limited to printable ASCII and checked user-code-page pointers. [M5-F3 independent native acceptance evidence](docs/M5_HTML_MULTI_REPORT.md).

## Run a separate ROMFS user program in native Ring 3 (M5-C1)

This opt-in test assembles `examples/user-programs/hello.S` into a small, checked `HKEX` executable and embeds it as `/apps/hello.hke` in the native kernel's immutable ROMFS. After bounded file validation the kernel loads **actual independent machine-code bytes** into a private CPL3 code page, checks register-only system calls, returns to generated HTML code and reclaims the user frames. To reproduce:

```sh
python3 scripts/build_boot.py --exception-idt --tss-ist --user-loader-probe --test-exit --out build/html-kernel-m5-user.iso
python3 scripts/test_m5_user_loader.py
```

This is **not** HTML-to-user-executable compilation, an ELF loader, or M5-B's interactive shell. Actual QEMU boots include independent source mutations and CPU fault negative controls; see [M5-C1 contract](docs/M5_USER_LOADER.md).

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

## M4-C1 real user-mode experiment (QEMU, opt-in)

`python3 scripts/test_m4_user.py` builds and boots a native x86-64 ISO with a real CPL3 user task, checked INT 0x80 syscalls, user RO-code/RW-stack pages, and CPU #PF/#GP negative controls. It restores the kernel and executes HTML-generated source on the success path. This is **not** a general process loader or a release-ready security boundary; single static user task only. See [M4-C1 exact evidence and unsupported modes](docs/M4_RING3_C1.md).

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

## M3 one-shot recoverable page fault and physical-frame ownership

An opt-in M3 experiment now tracks 16 physical frames by TABLE/DATA owner (bounded claim, wrong-owner/double-free refusal, reclaimed reuse). With `--exception-idt --paging-probe --paging-recover-test`, one tightly scoped **real CPU #PF** on a reserved private 4KiB virtual alias allocates a zeroed page, updates its PTE and resumes the faulting instruction with `iretq`. The original CR3 is restored and all owned frames are released afterward. This is **not** general demand paging, a process-isolated virtual memory manager, or TSS/IST; unarmed/unauthorized faults still halt. See [M3_FAULT_RECOVERY.md](docs/M3_FAULT_RECOVERY.md). Run `python3 scripts/test_paging_recovery.py` and `python3 -m unittest tests.test_frame_owner -v`. No public Boot Lab ISO or physical hardware claims are made for this opt-in experiment.

## M3 dedicated CPU fault stacks (TSS/IST, opt-in)

The kernel now has a native x86-64 TSS/GDT option with dedicated IST1 stack for double faults and IST2 for page faults. Genuine BIOS QEMU tests show vector8 (#DF) switches to the emergency IST1 stack when a test-only damaged IST2 causes exception delivery to fail. A normal #PF uses IST2 and can still exercise the narrow one-shot zero-page recovery described above. Use `python3 scripts/test_tss_ist.py`, or build an opt-in native image with `python3 scripts/build_boot.py --exception-idt --tss-ist --out build/html-kernel-m3-ist.iso`. This is not an IRQ driver, a general-purpose virtual memory manager, or evidence of real hardware boot. See [M3_TSS_IST.md](docs/M3_TSS_IST.md).

## M3 repeated multi-page native memory proof

A further opt-in proof maps three extra 4KiB virtual aliases under a private CR3, uses actual CPU loads/stores cross-checked through Limine's HHDM, unmaps and releases each owned frame, then **repeats three times**. The CPU must fault at a revoked alias with the precise CR2 address and a non-success QEMU exit. A combined native boot runs this with the TSS/IST stacks, bounded first-page fault recovery and real RGB console. Use `python3 scripts/test_multimap.py` or `python3 scripts/build_boot.py --exception-idt --tss-ist --paging-probe --multi-page-test --out build/html-kernel-m3-multimap.iso`. [M3 bounded multi-page proof](docs/M3_MULTIPAGE.md). This supports the project’s **bounded QEMU M3 acceptance**, not general memory/process management, real hardware support or a complete OS.

## Boot Lab — view the real boot from the first BIOS event

The public [Boot Lab](https://eun-si123.github.io/html-kernel-os/play.html) can display the guest's observed SeaBIOS VGA boot text separately from the **live, raw COM1 bytes** emitted by the source-derived x86-64 kernel. Before starting, choose the real-VM observation mode (v86 run/stop pacing, not CPU underclocking) or normal speed. You can pause/resume the actual guest CPU; post-boot replay remains separate. The viewer loads the exact example HTML source compiled into the selected ISO and highlights source `<print>` lines only where the **actual output literal** matches. Source code is packaged alongside the site, *not* stored as source in the ISO: that ISO contains an ELF machine-code kernel, the pinned Limine bootloader and configuration. See [Boot Lab observation limitations](docs/BOOT_LAB_LIVE_TRACE.md).

## Stop a nonyielding user program with a real CPU timer (M5-E2)

For Ubuntu with QEMU and GCC, run `python3 scripts/run_m5_console.py --with-user-program --recover-user-faults --user-timeout`. In the live COM1 console, type `run /apps/spin.hke`: its Ring3 machine code **never yields**, but a genuine x2APIC local timer IRQ retires the user program after a bounded four-tick budget and returns to `M5_PROMPT>`. Then `run /apps/hello.hke` and `exit` still work. Verify with `python3 scripts/test_m5_user_timeout.py`; see [actual CPU proof and limitations](docs/M5_USER_TIMEOUT.md). This mode requires an x2APIC QEMU CPU, is a narrow experiment and is not safe general-purpose user process support.

**M5-E3 process lifecycle regression:** `python3 scripts/test_m5_process_lifecycle_stress.py` interleaves successful Ring3 executions, actual x2APIC timeouts, CPU exception recovery and invalid syscall recovery on a live QEMU UART shell, three full boots. See [M5-E3 test contract](docs/M5_PROCESS_LIFECYCLE_STRESS.md). This is not a full security audit or hardware compatibility claim.

**M5-E3-B CPU user-trap containment (experimental):** real x86-64 CPL3 `DIV/0` (#DE), `ICEBP` (#DB) and `INT3` (#BP) now abort only the active known HKEX program in the opt-in guarded recovery mode, preserving the live COM1 shell. Run `python3 scripts/test_m5_user_trap_containment.py` to check true QEMU CPU delivery, one-byte trap-end RIP, healthy reruns, original M5-D1 fatal behavior and active x2APIC integration. See [M5 user fault contract](docs/M5_USER_FAULT_RECOVERY.md). This is not full arbitrary-user-program safety or a general debugger.

**M5-E3-C guarded user syscall frame (experimental):** a separate Ring3 HKEX program can deliberately corrupt its own RSP before `INT 0x80`; only an independently verified live user owner/privilege/TSS/CR3 context permits per-program retirement. The COM1 prompt and next HTML-compiled user program survive. Run `python3 scripts/test_m5_user_syscall_frame.py` for genuine CPU/COM1 QEMU and pre-fix fail-stop comparison; [exact limits](docs/M5_USER_SYSCALL_FRAME.md). This is not full untrusted-program safety.

**M5-E3-D malformed user stack during timer IRQ (opt-in):** a recognized Ring3 program that clobbers its own stack pointer and spins can now be retired through an actual x2APIC interrupt **without killing the COM1 shell**, but only after an independent trusted TSS/CR3/owner context proof. Existing normal four-tick preemption and unsupported CPU fail-stop are preserved. `python3 scripts/test_m5_user_bad_irq.py` runs three entire QEMU boots with 12 corrupt-stack task terminations and 15 separately HTML-compiled text user program reruns; [exact limitations](docs/M5_USER_BAD_IRQ.md). This remains experimental QEMU-only code.

### M5-F4 — read a user program's exit code

A trusted HTML user program can finish with `<halt code="7"/>` (ASCII decimal `0..255`). Compile it using `python3 scripts/run_m5_console.py --html-user-app path/to/user.html`, then enter `run /apps/hello.hke` on QEMU COM1. After private Ring3 task cleanup, status `0` keeps `M5_RUN_DONE`; status `7` prints `M5_RUN_EXIT_CODE=7`. Bad or out-of-range exit statuses are rejected without killing the guarded UART shell. [Exact QEMU tests and limitations](docs/M5_HTML_EXIT_STATUS.md).

### M5-F5 — print the entire unsigned 64-bit range from HTML

The optional HTML user-program target can now emit full `u64` numeric results through actual Ring3 `INT 0x80` and native COM1, including `18446744073709551615`. Try `python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-u64-report.html` and enter `run /apps/hello.hke`. The kernel still limits each app to eight reports and rejects invalid code and non-owned user memory; legacy assembly modes keep their older <=9999 ABI. [Real QEMU test, implementation and caveats](docs/M5_HTML_U64_OUTPUT.md).

**M5-E3-E poisoned user stack during #UD (experimental):** a loaded Ring3 app that overwrites its own RSP and executes a genuine `UD2` can now be retired without killing the native COM1 shell, **only** after an independent CPU #UD frame/TSS/CR3/owner proof. The original healthy task strict validation and legacy fail-stop remain; `python3 scripts/test_m5_user_bad_ud_stack.py` covers real QEMU no-timer/x2APIC modes, four invalid stack registers, clean owner reclamation and healthy HTML user reruns. [Full verified boundaries](docs/M5_USER_BAD_UD.md). Not a general-purpose untrusted-code sandbox.

**M5-E3-F controlled CPU divide-error recovery:** after a known Ring3 program damages its own stack pointer, a genuine divide-by-zero exception can be recovered with the same exact TSS.RSP0/CR3/owner proof as M5-E3-E #UD, without broadening any error-code or trap vector. `python3 scripts/test_m5_user_bad_de_stack.py` proves real QEMU process retirement, healthy HTML app reruns, old mode rejection and actual timer coexistence; [details](docs/M5_USER_BAD_DE.md). Experimental trusted images only, not a general security sandbox.

### Live M5 — HTML 프로그램을 실제 CPU에서 부팅/실행

[전용 GitHub Pages 실행실](https://eun-si123.github.io/html-kernel-os/live/)은 기존 Boot Lab과 분리되어 있으며, **빌드 때 HTML 원본을 네이티브 Ring3 사용자 코드로 컴파일**한 Limine ISO를 브라우저의 x86-64 에뮬레이터에서 실제로 부팅하도록 구성했어. ROMFS의 실행 파일을 COM1에서 `run /apps/hello.hke`로 실행해 64비트 출력과 종료 코드 7을 확인할 수 있어. 사이트의 입력은 실제 게스트 UART에 전달되며, JavaScript 출력 재생이나 표준 HTML의 직접 CPU 실행이 아님. Chromium 158 개발 프리뷰에서 실제 SeaBIOS/VGA→COM1→Ring3 앱 2회→​종료까지 확인했으며, 공개 GitHub Pages에서도 실제 SeaBIOS/COM1 → Ring3 프로그램 2회/종료 코드 7/프레임 회수/커널 `exit`까지 확인했어 (PR #96, Pages `45153958869` 성공). [빌드/호환성/한계](docs/M5_WEB_LIVE.md).

**M5-E3-G corrupted Ring3 RSP and genuine CPU #GP:** an owned user program doing privileged I/O after destroying its own RSP no longer needs to kill the entire opt-in UART shell. The separately validated 48-byte x86 exception **error-code frame** and CR3/TSS owner proof admits only genuine CPL3 #GP for a live current task; pure GCC UBSan and repeated native QEMU tests prove wrong frames and old mode still reject. See [exact limitations](docs/M5_USER_BAD_GP.md).

**HTML source inside the native OS (M5 Web-Live B):** on the [browser live VM](https://eun-si123.github.io/html-kernel-os/live/), the `cat /source.html` command reads the exact HTML source bytes from the **kernel's real ROMFS**; the browser compares it to the SHA-256-checked public source. `run /apps/hello.hke` then executes the native Ring3 program compiled from those bytes, with real UART output and exit status. This is not a fake JavaScript program or a claim that the CPU directly parses standard HTML. [Evidence & limits](docs/M5_WEB_LIVE.md).

**M5-E3-H CPU page-fault containment (experimental):** a genuine page fault on the CPU's **TSS.IST2** stack after a known Ring3 app corrupts its own stack pointer can now retire *that one* app and resume the live UART shell only if the complete IST2 CPU error frame and process owner are independently verified. QEMU proves actual PF error5/7 recovery and narrowly scoped fail-stop negatives. [Boundaries and tests](docs/M5_USER_BAD_PF.md). This is not a general untrusted-program security guarantee.

**M5-E3-I trap-class bad-RSP recovery (experimental):** true CPU #DB/ICEBP and #BP/INT3 after a known Ring3 app poisons RSP can retire that one process without killing the interactive UART console, but **only** after exact CPU TSS.RSP0 five-qword frame and private process ownership checks. Unlike a fault, the saved trap RIP may be exactly code-end. Actual x2APIC QEMU three-boot, no-timer and legacy fail-stop controls plus GCC UBSan negatives are documented in [M5-E3-I proof](docs/M5_USER_BAD_TRAP.md). Not an arbitrary-app sandbox.

**M5 Web-Live C — your own HTML code on real virtual CPU (experimental):** edit a local HTML-shaped user program and compile it with `python3 scripts/build_live_site.py --source ./my-program.html --out-dir ./build/my-html-os`. In the [live native boot lab](https://eun-si123.github.io/html-kernel-os/live/) choose the created ISO and its matching HTML using the local file inputs; the browser actually boots **the locally built native ISO** (no uploading), `cat /source.html` checks the exact guest ROMFS bytes, and `run /apps/hello.hke` executes the user's compiled Ring3 app. Genuine QEMU and isolated Chromium verified a **changed 64-bit output and exit code 9** against the original code 7. GitHub Pages is still **not** an in-browser HTML-to-ISO compiler; use your local toolchain. [Reproducible steps and limits](docs/M5_WEB_LOCAL_ISO.md).
