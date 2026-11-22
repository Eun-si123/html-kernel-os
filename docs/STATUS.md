# HTML Kernel OS — current state

**Baseline:** 2026-11-22, initial public prototype (commit `42d0a9c`). Later commits can change this; always compare with the current default branch and CI. This page records only evidence observed or present in the repository, and should be updated when implementation changes.

| Capability | Baseline status | Evidence / limitation |
| --- | --- | --- |
| Restricted HTML-like grammar parsing | IMPLEMENTED (prototype) | `compiler/htmlk.py`, `tests/test_compiler.py` |
| `<print>` and `<halt/>` C generation | IMPLEMENTED (prototype) | UTF-8 bytes sent to x86 I/O port 0xE9 in generated source |
| Freestanding x86-64 object compilation | LOCAL PASS (baseline) | `build/kernel.o` was verified as ELF x86-64 relocatable object locally; CI also compiles sample |
| Parser tests | LOCAL PASS / CI PASS (baseline) | Seven tests at initial public release; see exact CI revision for new claims |
| Static website source | IMPLEMENTED (source only) | `site/`; no claim of real kernel demo |
| Browser-side compiler or kernel emulator | NOT IMPLEMENTED | Website is informational only |
| Linker/bootloader integration | NOT IMPLEMENTED | No bootable ISO/UEFI image |
| QEMU kernel boot | NOT RUN | No bootable kernel available |
| Physical PC boot | NOT RUN | No tested machine image |
| Memory, interrupts, tasks, filesystems, drivers | NOT IMPLEMENTED | Architecture-level ambitions only |
| GitHub Pages deployment | NOT VERIFIED / NOT AUTHORIZED BY DEFAULT | `site/` is deployment-ready source, not proof of a publicly running Pages site |

## Evidence classes

- **SOURCE:** checked-in code, docs, parser tests.
- **LOCAL BUILD:** executable command and observable compiler artifact from a named environment.
- **CI:** passing run tied to exact commit SHA and job; only covers steps actually run.
- **QEMU BOOT:** real bootable artifact, captured boot log and exit assertion in an emulator.
- **PHYSICAL BOOT:** exact hardware/firmware target, reproducible observed log, and recovery safeguards.

These are not interchangeable. CI can verify code generation without proving a kernel was executed. Use [VALIDATION.md](VALIDATION.md) for criteria.

## Next acceptance gate

**Milestone M1 ([ROADMAP.md](ROADMAP.md)):** Build a **bootable x86-64 kernel image** from the HTML-derived code through a pinned and verifiable bootloader/linker arrangement. Require an automated QEMU boot log and deterministic, checkable output before marking this gate complete. [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) holds proposed Python-like language ergonomics; [PROJECT_RISKS.md](PROJECT_RISKS.md) holds risks, neither counts as implementation evidence.

This gate does not imply that memory management, a scheduler, applications, or a full OS already exist.

## Site and licensing

The `site/` directory contains source code for a separate project website. Avoid changing another `github.io` repository or enabling Pages without explicit authorization. No repository license has yet been selected, so public visibility alone does not grant open-source reuse rights.
