# HTML Kernel OS — current state

**Baseline:** 2026-11-22, initial public prototype (commit `42d0a9c`). Later commits can change this; always compare with the current default branch and CI. This page records only evidence observed or present in the repository, and should be updated when implementation changes.

| Capability | Baseline status | Evidence / limitation |
| --- | --- | --- |
| Restricted HTML-like grammar parsing | IMPLEMENTED (prototype) | `compiler/htmlk.py`, `tests/test_compiler.py` |
| `<print>` and `<halt/>` C generation | IMPLEMENTED (prototype) | UTF-8 bytes sent to x86 I/O port 0xE9 and COM1 0x3f8; both tested locally in QEMU |
| Freestanding x86-64 object compilation | LOCAL PASS (baseline) | `build/kernel.o` was verified as ELF x86-64 relocatable object locally; CI also compiles sample |
| Parser / static-site tests | LOCAL PASS / CI PASS | 13 source/site Python tests at PR #16; see exact CI revision for new claims |
| Project website source | IMPLEMENTED / DEPLOYED | `site/` is a public Pages site with native x86-64 browser boot lab; not a desktop OS |
| Browser-based x86-64 emulator page | LIVE BOOT PASS (one Chromium/Playwright environment) | Public https://eun-si123.github.io/html-kernel-os/play.html, user-clicked boot loads v64 WASM, receives exact HTML-derived COM1 bytes `Hello from HTML Kernel!\nNative code, not a browser.\n`; no browser console errors in tested session. Mobile and other browsers NOT TESTED |
| M2 numeric variables and control flow (first slice) | LOCAL + CI QEMU PASS / Browser M2 PASS | compiler/language.py and compiler/htmlk.py; typed u64 variables, + - * expressions, bounded repeat, if comparisons, numeric print; examples/math-kernel.html booted with expected output; PR #18 CI run 45033324433 PASS, browser math demo also read exact COM1 output on Pages run 45033402277. Pure function evidence is in the row below; more advanced data types NOT IMPLEMENTED |
| M2 reusable pure u64 functions | LOCAL + CI + BROWSER BOOT PASS | Pure typed u64 functions (0..4 parameters), nested calls, forward definitions, recursion/depth/work checks. `scripts/test_functions.py` real Linux + QEMU original/modified output and negative controls pass; merged PR #20 CI push run 45035430468 and PR run 45035455198 SUCCESS. Main CI 45035522696 SUCCESS; Pages build+deploy 45035522693 SUCCESS. Connected Chromium/Playwright selected `functions` on public play.html and received exact COM1 bytes `Functions in HTML Kernel!\n13\n17\nfunction PASS\n10\n12\n`; console 0 errors. Other browsers/mobile and physical hardware NOT TESTED |
| M2 scoped function bodies | LOCAL QEMU + LINUX PASS / CI PENDING | `compiler/function_codegen.py`: lexical variable scopes, nested `let`/`set`, bounded `if`/`repeat`, mandatory final typed return, optional nested early returns, no globals/side-effects. `examples/scoped-functions-kernel.html`, `scripts/test_scoped_functions.py`: real QEMU and native Linux original/changed function results (25,10 vs 22,10), invalid return/scope and wrong output rejection; branch CI and Pages/browser NOT YET TESTED |
| Linux userland program from shared HTML-like language | LOCAL + CI PASS (PR #19) | Same parser and M2 math source compiled to a normal unprivileged x86-64 Linux executable, executes with correct stdout and exit code 0; mutation and malformed-input negative control in scripts/test_linux.py; NO Linux OS/desktop implemented |
| Linker/bootloader integration | LOCAL PASS | `boot/`, `scripts/build_boot.py`; pinned Limine 12.11.1 and protocol header, generated ELF + hybrid bootable ISO |
| QEMU kernel boot | LOCAL PASS + CI PASS (M1) | `scripts/test_boot.py` real x86_64 BIOS QEMU, original and altered HTML source both boot; debugcon output + exit code 33; negative controls pass. GitHub PR #13 Actions run `45027891902` SUCCESS and main run `45029073618` SUCCESS |
| Physical PC boot | NOT RUN | Browser emulation and QEMU do not establish physical hardware support |
| Memory, interrupts, tasks, filesystems, drivers | NOT IMPLEMENTED | Architecture-level ambitions only |
| Project-scoped GitHub Pages deployment | DEPLOYED / LIVE PASS | Project path https://eun-si123.github.io/html-kernel-os/ has HTTP 200 and actual browser boot verified, workflow run `45029073658` SUCCESS. Existing personal `github.io` repository not modified |
| C++/Rust-class native performance | GOAL / NOT BENCHMARKED | See [PERFORMANCE.md](PERFORMANCE.md); no comparable workloads or reproducible timing evidence yet |

## Evidence classes

- **SOURCE:** checked-in code, docs, parser tests.
- **LOCAL BUILD:** executable command and observable compiler artifact from a named environment.
- **CI:** passing run tied to exact commit SHA and job; only covers steps actually run.
- **QEMU BOOT:** real bootable artifact, captured boot log and exit assertion in an emulator.
- **PHYSICAL BOOT:** exact hardware/firmware target, reproducible observed log, and recovery safeguards.

These are not interchangeable. CI can verify code generation without proving a kernel was executed. Use [VALIDATION.md](VALIDATION.md) for criteria.

## Next acceptance gate

**M1 gate COMPLETE**: reproducible HTML-derived Limine ISO, real headless QEMU BIOS boot, modified-source provenance and negative tests all PASS both locally and in GitHub Actions (PR #13 run `45027891902`; current main CI run `45029073618`). **M2 is NEXT**: real variables, typed expressions, branches, loops and functions with actionable diagnostics. Browser boot is also independently confirmed in one Chromium environment. [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) holds proposed Python-like language ergonomics; [PROJECT_RISKS.md](PROJECT_RISKS.md) holds risks, neither counts as implementation evidence.

This gate does not imply that memory management, a scheduler, applications, or a full OS already exist. The confirmed interview Q1–Q20 goals and independently testable Linux/browser paths are in [INTERVIEW_DECISIONS.md](INTERVIEW_DECISIONS.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Site and licensing

The `site/` directory contains source code for a separate project website. Avoid changing another `github.io` repository or enabling Pages without explicit authorization. No repository license has yet been selected, so public visibility alone does not grant open-source reuse rights.
