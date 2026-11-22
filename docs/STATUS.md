# HTML Kernel OS — current state

**Baseline:** 2026-11-22, initial public prototype (commit `42d0a9c`). Later commits can change this; always compare with the current default branch and CI. This page records only evidence observed or present in the repository, and should be updated when implementation changes.

| Capability | Baseline status | Evidence / limitation |
| --- | --- | --- |
| Restricted HTML-like grammar parsing | IMPLEMENTED (prototype) | `compiler/htmlk.py`, `tests/test_compiler.py` |
| `<print>` and `<halt/>` C generation | IMPLEMENTED (prototype) | UTF-8 bytes sent to x86 I/O port 0xE9 and COM1 0x3f8; both tested locally in QEMU |
| Freestanding x86-64 object compilation | LOCAL PASS (baseline) | `build/kernel.o` was verified as ELF x86-64 relocatable object locally; CI also compiles sample |
| Parser tests | LOCAL PASS / CI PASS (baseline) | Seven tests at initial public release; see exact CI revision for new claims |
| Static website source | IMPLEMENTED (source only) | `site/`; no claim of real kernel demo |
| Browser-based x86-64 emulator page | IMPLEMENTED (source, BROWSER BOOT NOT YET VERIFIED) | `site/play.html`, `site/play.js`; pinned v64 x86-64 WASM module is configured to load generated ISO and read COM1; browser runtime must be separately verified |
| Linux userland program from shared HTML-like language | NOT IMPLEMENTED | Current emitted `outb` code is freestanding/QEMU-specific, not a Linux userspace executable |
| Linker/bootloader integration | LOCAL PASS | `boot/`, `scripts/build_boot.py`; pinned Limine 12.11.1 and protocol header, generated ELF + hybrid bootable ISO |
| QEMU kernel boot | LOCAL PASS (CI PENDING) | `scripts/test_boot.py` real QEMU x86_64 BIOS: original and changed HTML source both boot; debugcon output + exit code 33; negative output/invalid source controls pass. Local log in external HDD, to be verified on CI exact PR SHA |
| Physical PC boot | NOT RUN | Browser emulation and QEMU do not establish physical hardware support |
| Memory, interrupts, tasks, filesystems, drivers | NOT IMPLEMENTED | Architecture-level ambitions only |
| Project-scoped GitHub Pages deployment | USER REQUESTED / PENDING | Project path `/html-kernel-os/` authorized by user; distinct from existing personal `github.io` repository, which must remain unchanged; check actual live deployment and browser boot before claiming success |
| C++/Rust-class native performance | GOAL / NOT BENCHMARKED | See [PERFORMANCE.md](PERFORMANCE.md); no comparable workloads or reproducible timing evidence yet |

## Evidence classes

- **SOURCE:** checked-in code, docs, parser tests.
- **LOCAL BUILD:** executable command and observable compiler artifact from a named environment.
- **CI:** passing run tied to exact commit SHA and job; only covers steps actually run.
- **QEMU BOOT:** real bootable artifact, captured boot log and exit assertion in an emulator.
- **PHYSICAL BOOT:** exact hardware/firmware target, reproducible observed log, and recovery safeguards.

These are not interchangeable. CI can verify code generation without proving a kernel was executed. Use [VALIDATION.md](VALIDATION.md) for criteria.

## Next acceptance gate

**Milestone M1 ([ROADMAP.md](ROADMAP.md)):** Local image build, headless x86-64 BIOS QEMU boot, HTML-derived debugcon/COM1 output, source-mutation and negative controls **PASS**. The independent GitHub CI run for the exact integration PR is still required before accepting the milestone as repository-wide COMPLETE. [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) holds proposed Python-like language ergonomics; [PROJECT_RISKS.md](PROJECT_RISKS.md) holds risks, neither counts as implementation evidence.

This gate does not imply that memory management, a scheduler, applications, or a full OS already exist. The confirmed interview Q1–Q20 goals and independently testable Linux/browser paths are in [INTERVIEW_DECISIONS.md](INTERVIEW_DECISIONS.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Site and licensing

The `site/` directory contains source code for a separate project website. Avoid changing another `github.io` repository or enabling Pages without explicit authorization. No repository license has yet been selected, so public visibility alone does not grant open-source reuse rights.
