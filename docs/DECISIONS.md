# Decision register — HTML Kernel OS

Only user-confirmed decisions belong under **Confirmed**. Proposals are not blanket permission to deploy, change GitHub settings, or claim functionality.

## Confirmed

- **Primary experiment:** write kernel/OS behavior using HTML-like syntax that can ultimately execute natively; a browser-only visual OS is insufficient.
- **Public repository:** the experiment is published in a separate public repository `Eun-si123/html-kernel-os`.
- **Personal GitHub site safety:** preserve the existing `github.io` site and use separate project-scoped testing rather than overwriting the personal homepage.
- **Cross-agent consistency:** align the agent discovery and evidence conventions with TeamForge / BetterNet-App while keeping this repo's technical scope independent.
- **Implementation honesty:** a compiler prototype is not yet a complete kernel or OS; public docs must label it accordingly.
- **Performance goal (2026-11-22):** aim for compiled native execution speed comparable to C++/Rust while keeping common programming tasks beginner-friendly like Python. This is a **goal, not measured performance**; see [PERFORMANCE.md](PERFORMANCE.md).

## Proposals / not yet authorizations

- Exact bootloader/version and final compiler backend (C-as-IR versus LLVM/native code generation). See [ROADMAP.md](ROADMAP.md) M1; Limine is a candidate, not a pinned implementation yet.
- **Benchmark threshold and protocol specifics:** a numeric C++/Rust ratio, allowed toolchain versions and workloads require representative implemented constructs and measured baselines; nothing has yet been benchmarked.
- Exact language grammar and Python-level usability target: syntax rules, error behavior, expressions, type/ownership/unsafe contract, safe kernel libraries, and required novice comparison. See [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md); example proposed tags are **not implemented**.
- Timeline and resource commitment of M1–M6; the roadmap sets **dependencies and acceptance criteria**, not agreed delivery dates or guaranteed feasibility.
- Hosting a live preview via GitHub Pages: the user has discussed using `github.io` for testing, but a Pages activation is a distinct repository-setting/deployment change. Check current explicit authorization and impact before enabling.
- Operating-system scope beyond a bootable demonstrator (hardware targets, driver scope and API contracts).
- Open-source license selection, release publishing, package distribution, third-party contributions and security policy.

When a choice becomes confirmed, record the change and rationale here, update impacted authoritative documents, and avoid silently treating a proposal as implementation.
