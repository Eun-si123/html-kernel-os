# HTML Kernel OS

**An experiment to express native kernel behavior with HTML-like syntax.**

HTML is normally a document language. This repository explores a dedicated compiler that interprets a restricted set of HTML-style elements as *systems-programming instructions*. The long-term goal is a self-booting OS whose kernel logic is written in that language.

> **Current status (prototype 0.1): NOT A BOOTABLE OS.** The proof of concept converts a tiny HTML dialect to freestanding x86-64 C source. GCC can compile this source to an object file. It has **not** been linked to a bootloader or executed as a kernel. There is no memory manager, filesystem, scheduler, or hardware driver implementation.

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

The files under site/ are ready for **local preview only**. No GitHub Pages domain, existing username.github.io repository, Pages configuration, or deployment workflow is used. GitHub Pages may be configured separately for testing in the future.

Local preview:

~~~bash
python3 -m http.server 8000 --directory site
~~~

Then open http://127.0.0.1:8000 in your browser.

## Scope and naming

"HTML kernel" is shorthand for a **new programming language with HTML-like syntax**. This is not standard HTML, not a browser engine, and not an existing production OS. A source language written in angle brackets still needs a compiler and a CPU-executable entry point.

## License

**No license has been selected yet.** Public visibility does not grant open-source reuse rights by itself; a license decision should be made before encouraging outside contributions.
