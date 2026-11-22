# HTML Kernel OS

**An experiment to express native kernel behavior with HTML-like syntax.**

HTML is normally a document language. This repository explores a dedicated compiler that interprets a restricted set of HTML-style elements as *systems-programming instructions*. The long-term goal is a self-booting OS whose kernel logic is written in that language.

> **Current status: VERIFIED BOOTABLE DEMO KERNEL (QEMU BIOS + browser), NOT A USABLE OS.** A restricted HTML dialect compiles to freestanding x86-64 C; Limine starts the generated kernel. Real QEMU source-mutation/negative controls passed locally and on GitHub CI. The same boot ISO was independently booted in Chromium using the v64 WebAssembly x86-64 emulator: [try the browser demo](https://eun-si123.github.io/html-kernel-os/play.html). UEFI, mobile-browser compatibility and physical hardware remain unverified. No memory manager, filesystem, scheduler or general hardware drivers.

## Agent and contributor entry points

AI agents and external contributors: start at **[AGENTS.md](AGENTS.md)**, then follow **[CODEMAP.md](CODEMAP.md)** and the [documentation hub](docs/README.md). The repository uses TeamForge/BetterNet-style instructions for task ownership, public-safe commit attribution, current status, durable memory and advisory [feature-to-regression mapping](agent-evals/README.md). The instructions do not start a background agent or imply automatic deployment.

Read [actual implementation status](docs/STATUS.md) and [evidence criteria](docs/VALIDATION.md) before claiming native boot support. See [current decisions](docs/DECISIONS.md) for confirmed versus proposed scope. The [founder interview record](docs/INTERVIEW_DECISIONS.md) captures Q1–Q20: the reusable HTML-like language and usable Linux-based prototype remain design goals; a **minimal independent kernel and browser boot experiment** now run, but not a full OS. The [implementation plan](docs/IMPLEMENTATION_PLAN.md) prioritizes actual QEMU boot proof and a reusable language core.

## Roadmap for people and agents / 개발 계획

Start with the **[M0–M6 milestone roadmap](docs/ROADMAP.md)**: M1 actual QEMU BIOS boot is **verified by local tests and GitHub CI**; M2 core language programming features are NEXT. Read the [language design / Python ease comparison](docs/LANGUAGE_DESIGN.md), [C++/Rust-class performance goal and measurement contract](docs/PERFORMANCE.md), and [risk/assumption register](docs/PROJECT_RISKS.md) before proposing syntax or hardware changes. Milestones are *not* dates or release promises; [STATUS](docs/STATUS.md) owns observed progress. Agents can open milestone-scoped Issues with [this shared task template](.github/ISSUE_TEMPLATE/roadmap-task.md).

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

The experimental language now accepts unsigned 64-bit variables, arithmetic (+, -, *), bounded repeat and if comparisons. For example, [math-kernel.html](examples/math-kernel.html) prints 14, 16, 18 from a native x86-64 kernel after compiling the HTML source. Functions, input and a full OS are still pending: **M2 is only partially implemented.**

To verify this locally with GCC, QEMU and xorriso, run:

~~~sh
python3 scripts/test_language_boot.py
python3 scripts/build_boot.py --source examples/math-kernel.html --out build/html-kernel-math.iso
~~~

The [language contract](docs/M2_LANGUAGE_CONTRACT.md) documents syntax, safety bounds and unsupported expressions. Once CI and Pages have passed, select the M2 arithmetic demo in the [web boot lab](https://eun-si123.github.io/html-kernel-os/play.html).

## Project layout

- compiler/htmlk.py — strict experimental HTML dialect parser / C generator
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
