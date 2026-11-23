# Decision register — HTML Kernel OS

Only user-confirmed decisions belong under **Confirmed**. Proposals are not blanket permission to deploy, change GitHub settings, or claim functionality.

## Confirmed

- **Primary experiment:** write kernel/OS behavior using HTML-like syntax that can ultimately execute natively; a browser-only visual OS is insufficient.
- **Public repository:** the experiment is published in a separate public repository `Eun-si123/html-kernel-os`.
- **Personal GitHub site safety:** preserve the existing `github.io` site and use separate project-scoped testing rather than overwriting the personal homepage.
- **Cross-agent consistency:** align the agent discovery and evidence conventions with TeamForge / BetterNet-App while keeping this repo's technical scope independent.
- **Implementation honesty:** a compiler prototype is not yet a complete kernel or OS; public docs must label it accordingly.
- **Performance goal (2026-11-22):** aim for compiled native execution speed comparable to C++/Rust while keeping common programming tasks beginner-friendly like Python. This is a **goal, not measured performance**; see [PERFORMANCE.md](PERFORMANCE.md).

- **Founder interview final (2026-11-22, Q1–Q20):** HTML-like language + independent OS as long-term goals; preserve HTML-like syntax where practical; prioritize OS/kernel language first; favor common compiler and shared language, with a Linux-based practical prototype and separately verified independent-kernel track in parallel. Prefer staged implementation, measured trade-offs, and existing toolchains. See [INTERVIEW_DECISIONS.md](INTERVIEW_DECISIONS.md) for the exact responses and unresolved choices. The first accepted milestone is source-derived **real QEMU boot**; then grow kernel features, adapting success criteria to observed evidence. Browser boot is now implemented and verified in Chromium on project Pages; Windows-friendly local launching and broader OS experience remain future goals. Details, deferred choices, and measurable slices: [INTERVIEW_DECISIONS.md](INTERVIEW_DECISIONS.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). These are design goals, not currently implemented functionality.

- **Language direction (2026-11-23):** the founder welcomes developing the HTML-shaped syntax into a *complete programming language*, not merely a toy markup-to-kernel demonstration. Familiarity for people who work with HTML is a desired advantage, not an established usability result. Preserve HTML-like structure where it helps, but validate readability, actual learning effort and backend safety instead of claiming automatic ease.

## Proposals / not yet authorizations

- **M3 on-screen console (implemented in experimental PR #39):** request a Limine framebuffer only for an explicit video ISO; support validated 32-bit RGB, render a small original ASCII bitmap font, and keep COM1 as an independent fallback. A working QEMU monitor screenshot is necessary before claiming an on-screen result; public v86 presentation, keyboard input and language syntax design remain separate unapproved changes. The freestanding GCC CPU architecture must be pinned to x86-64 baseline (prevent unsupported BMI2 SHLX).

- **M2 array safety semantics (proposed 2026-11-23):** support bounded 1..64-element, zero-initialized per-scope arrays without raw pointer escape; literal out-of-bounds accesses fail at compile-time, computed out-of-bounds accesses fatally trap with distinct kernel/Linux markers. This does **not** establish full memory safety, and runtime or syntax changes need deliberate review. The implementation remains an independent PR until verified.


- **M2 integer division semantics (2026-11-23, proposed, implemented in an unmerged branch):** use C-style integer `/` (truncate toward zero) and `%` (remainder matches dividend sign), reject literal zero, trap dynamic zero, define `INT_MIN/-1` wrap and zero remainder. Tests and a source-derived QEMU artifact demonstrate behavior but do not by themselves finalize the language specification. Python `//` remains unsupported due to conflicting rounding expectations. See [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md) and the PR before standardizing this choice.


- **Future compiler backend** (C-as-IR versus LLVM/native code generation): not decided. The *current* boot path uses pinned Limine v12.11.1 with a verified x86-64 BIOS QEMU boot; UEFI and physical hardware support are still unverified.
- **Benchmark threshold and protocol specifics:** a numeric C++/Rust ratio, allowed toolchain versions and workloads require representative implemented constructs and measured baselines; nothing has yet been benchmarked.
- Exact language grammar and Python-level usability target: syntax rules, error behavior, expressions, type/ownership/unsafe contract, safe kernel libraries, and required novice comparison. See [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md); example proposed tags are **not implemented**.
- Timeline and resource commitment of M1–M6; the roadmap sets **dependencies and acceptance criteria**, not agreed delivery dates or guaranteed feasibility.
- GitHub Pages deployment details beyond the user-authorized project-scoped `/html-kernel-os/` website (for example private hosting, domain changes, billing, or replacement of existing personal `github.io` homepage). Project Pages activation for this public repository is user-requested.
- Operating-system scope beyond a bootable demonstrator (hardware targets, driver scope and API contracts).
- Open-source license selection, release publishing, package distribution, third-party contributions and security policy.

When a choice becomes confirmed, record the change and rationale here, update impacted authoritative documents, and avoid silently treating a proposal as implementation.
