# HTML Kernel OS

**An experiment to express native kernel behavior with HTML-like syntax.**

HTML is normally a document language. This repository explores a dedicated compiler that interprets a restricted set of HTML-style elements as *systems-programming instructions*. The long-term goal is a self-booting OS whose kernel logic is written in that language.

> **Current status: BOOTABLE DEMO KERNEL (local QEMU BIOS PASS), NOT A USABLE OS.** A restricted HTML dialect compiles to freestanding x86-64 C; Limine hands off to the generated kernel. Real QEMU output and source-change/negative controls passed locally. GitHub CI, UEFI, browser emulator, and physical hardware require separate observed evidence. No memory manager, filesystem, scheduler or general hardware drivers.

## Agent and contributor entry points

AI agents and external contributors: start at **[AGENTS.md](AGENTS.md)**, then follow **[CODEMAP.md](CODEMAP.md)** and the [documentation hub](docs/README.md). The repository uses TeamForge/BetterNet-style instructions for task ownership, public-safe commit attribution, current status, durable memory and advisory [feature-to-regression mapping](agent-evals/README.md). The instructions do not start a background agent or imply automatic deployment.

Read [actual implementation status](docs/STATUS.md) and [evidence criteria](docs/VALIDATION.md) before claiming native boot support. See [current decisions](docs/DECISIONS.md) for confirmed versus proposed scope. The [founder interview record](docs/INTERVIEW_DECISIONS.md) captures Q1–Q20: the shared HTML-like language, Linux-based prototype, independent kernel, and browser-accessible experience are goals, not shipped features. The [implementation plan](docs/IMPLEMENTATION_PLAN.md) prioritizes actual QEMU boot proof and a reusable language core.

## Roadmap for people and agents / 개발 계획

Start with the **[M0–M6 milestone roadmap](docs/ROADMAP.md)**: M1 actual QEMU BIOS boot passed locally and needs independent PR CI evidence before claiming repository-wide completion. Read the [language design / Python ease comparison](docs/LANGUAGE_DESIGN.md), [C++/Rust-class performance goal and measurement contract](docs/PERFORMANCE.md), and [risk/assumption register](docs/PROJECT_RISKS.md) before proposing syntax or hardware changes. Milestones are *not* dates or release promises; [STATUS](docs/STATUS.md) owns observed progress. Agents can open milestone-scoped Issues with [this shared task template](.github/ISSUE_TEMPLATE/roadmap-task.md).

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

Generated C implements a function named kernel_main(). It uses the **QEMU debugcon I/O port 0xE9** to emit bytes, then halts. This function is **not connected to a real boot protocol** and is not suitable for arbitrary hardware without further work. The Python compiler is a *development tool*, not a runtime dependency of the generated object.

## Project layout

- compiler/htmlk.py — strict experimental HTML dialect parser / C generator
- examples/kernel.html — minimal source example
- tests/ — parser/codegen unit tests
- site/ — static promotional/technical site source, **not deployed**
- docs/ARCHITECTURE.md — design choices and explicit limitations
- .github/workflows/ci.yml — automated prototype checks

## Roadmap

1. [x] Define a minimal source grammar and compile to freestanding C.
2. [x] Add tests for good/bad inputs and object compilation.
3. [ ] Integrate with a verified x86-64 boot protocol (e.g., Limine); boot under QEMU with log output.
4. [ ] Add freestanding memory primitives and interrupt/exception handling.
5. [ ] Define systems semantics for tasks, drivers, I/O and more expressive HTML constructs.
6. [ ] Evaluate whether native codegen (or LLVM IR) is more sustainable than C-as-IR.

## Website / GitHub Pages

The user requested a **project-specific static GitHub Pages browser boot lab**, separate from the existing personal github.io homepage. After the Pages workflow succeeds, visit https://eun-si123.github.io/html-kernel-os/play.html to boot the generated ISO in a WebAssembly x86-64 emulator. The host is static: JavaScript runs the emulator on the visitor's machine, not on GitHub's servers. Actual browser boot success must be confirmed independently of the QEMU tests. The workflow builds and uploads the ISO and checksum-pinned v64 x86-64 WebAssembly emulator assets; the pinned emulator's ~4 MB of browser binaries are versioned in `site/vendor/` so GitHub Actions does not depend on third-party downloads. Browser emulator license in `site/v86-LICENSE.txt`.

Local preview:

~~~bash
python3 -m http.server 8000 --directory site
~~~

Then open http://127.0.0.1:8000 in your browser.

## Scope and naming

"HTML kernel" is shorthand for a **new programming language with HTML-like syntax**. This is not standard HTML, not a browser engine, and not an existing production OS. A source language written in angle brackets still needs a compiler and a CPU-executable entry point.

## License

**No license has been selected yet.** Public visibility does not grant open-source reuse rights by itself; a license decision should be made before encouraging outside contributions.
