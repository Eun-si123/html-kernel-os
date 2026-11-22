# HTML Kernel OS — development roadmap / 개발 로드맵

**Audience:** human contributors, beginner programmers, coding agents, reviewers.
**Project goal:** express increasingly capable **native OS/kernel logic** in an HTML-like systems language, while retaining a reproducible boot chain and honest execution evidence.

> **한국어 요약:** 지금은 `kernel.html → C 코드 → x86-64 오브젝트` 생성까지만 검증했어. 다음 목표는 이 오브젝트를 부트로더와 연결해 **QEMU에서 실제 커널로 부팅**하는 것(M1). 이후 언어 기능(M2), 메모리/인터럽트(M3), 작업/보호(M4), 최소 사용자 환경(M5), 실기기 검증(M6) 순으로 진행해. 실제 커널 부팅이 첫 성취 목표이며, **Linux 기반 시제품과 브라우저에서 체험하는 경로**도 장기 목표로 추가됐어. 브라우저 UI 시뮬레이션은 커널 부팅 증거가 아니야. 구체적인 병행 계획은 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)를 참고해.

## How to read this / 읽는 방법

- **Milestone ID `M0`…`M6`** is stable: use it in Issues, PRs, commits, checkpoints, and agent reports.
- **Acceptance gate** is the only definition of completion. A document, stub, generated object, or passing unit test alone cannot satisfy a boot/hardware gate.
- **Dependencies** are prerequisites, not permission to claim they passed. Implementation can be explored in parallel on separate branches; completing a later milestone still requires its prerequisites.
- **Current truth** lives in [STATUS.md](STATUS.md), actual source/tests, and GitHub CI. The roadmap describes goals and requirements; it is **not** an implementation scoreboard.
- Work on the **nearest unmet, unblocked milestone**, except for a confirmed high-priority correctness/security/privacy issue. Separate exploratory design from verified implementation.
- Each task needs a measurable outcome, a negative test/failure case, and explicit NOT RUN evidence classes. See [VALIDATION.md](VALIDATION.md).

## Founder interview Q1–Q20 and parallel delivery plan

The completed [founder interview](INTERVIEW_DECISIONS.md) confirms **D + E** success criteria: prove actual source-derived kernel boot first, then expand real HTML-language kernel functions and practical use; adjust later gates only with observed evidence. The [implementation plan](IMPLEMENTATION_PLAN.md) maps work into **P0–P5 execution slices**: language-core reliability, M1 boot, minimal Linux userspace target, language usability, browser/Windows demos, and existing M3–M6 kernel capabilities. **P-slices are planning workstreams, not replacement M-milestones or shipped features.**

The Linux and web delivery tracks do not remove QEMU M1 as the next native **boot** gate. Shared compiler semantics can be developed alongside boot integration. Any website/browser UI simulation must be labeled separately from real boot emulation.

## Milestone overview

| ID | Goal | Depends on | Acceptance gate / 완료 기준 |
| --- | --- | --- | --- |
| **M0** | HTML → freestanding native object | — | Parser tests + generated C + x86-64 object from the same source (baseline achieved; see STATUS) |
| **M1 — NEXT** | **Boot HTML-derived code in QEMU** | M0 | Reproducible x86-64 boot image; headless QEMU emits exact expected message from `kernel.html`; bounded automated PASS and negative FAIL |
| **M2** | Readable core programming language | M0; M1 for OS-integrated gate (design work can start earlier) | Variables, types, arithmetic, branches, loops, functions + safe diagnostics; representative source examples compile and run in the boot environment |
| **M3** | Memory and fault handling | M1, relevant M2 primitives | Memory map, bounded physical allocator and virtual mapping, deliberate fault evidence, repeatable QEMU tests |
| **M4** | Scheduling and privilege separation | M3 | Two distinct tasks execute deterministically; user/kernel isolation and bad-access rejection are demonstrable |
| **M5** | Minimal useful operating environment | M4 | Console input, small read-only initial filesystem, independent user program execution and reproducible tests |
| **M6** | Reliability + carefully scoped real-hardware trial | M5 | Recoverable, read-only-first physical test on an explicitly supported machine with reproducible observations; no untested hardware-wide support claim |

### M0 — source-to-object baseline (already evidenced)

- Current prototype supports `<kernel>`, `<onboot>`, `<print>`, `<halt/>` only; output targets **QEMU debugcon port 0xE9**, not a display driver.
- Acceptance: parse valid input; reject invalid structures; compile freestanding C with `-Werror`; verify the object format.
- **Does not prove:** bootloader linkage, QEMU execution, actual physical I/O, an OS, or general Python-level language features.
- References: [CODEMAP](../CODEMAP.md), [STATUS](STATUS.md).

### M1 — first *real* boot (highest engineering priority)

1. Choose/pin a verified **Limine** version and boot protocol; document artifact provenance and build prerequisites.
2. Define the correct kernel entry/linker layout; reuse the **HTML-generated `kernel_main`** and a minimal auditable handoff shim if required.
3. Build a bootable image in CI, not just an ELF relocatable object. Invoke headless QEMU with explicit machine options and `-debugcon` capture.
4. Confirm the **message originates from compiled `examples/kernel.html`**, not a hard-coded bootloader banner or test fixture.
5. Add deterministic timeout/halt outcome; test wrong/missing output and boot failure so a silent hang cannot pass.
6. Record exact commands, artifact SHA, log excerpt, source revision and CI link in STATUS/PR.

**Gate:** QEMU produces the expected message and a bounded automated test passes for an exact committed image.
**Not included:** RAM management, disk driver, real PC boot, graphical desktop, or hardware compatibility.
**Failure risks:** Limine protocol version mismatch, wrong memory mapping/link addresses, host-toolchain assumptions, debugcon incorrectly interpreted as screen output.

### M2 — easy-to-read but systems-capable language

1. Write a versioned [language design](LANGUAGE_DESIGN.md): grammar, nesting, attributes, names, expressions, whitespace, entities, Unicode, errors, versioning.
2. Implement a typed AST/semantic validation (no silent HTML browser error-recovery); accept/reject fixtures before native codegen.
3. Implement a minimal **documented** set of variables/constants, integer types, arithmetic, boolean conditions, bounded loops and functions; distinguish `safe` and explicit `unsafe` operations.
4. Add actionable errors with filename, line/column, invalid construct and suggestion.
5. Validate five beginner exercises, error paths and kernel/boot integration using the M1 harness.
6. Compare readability with Python based on real examples; do **not** claim "Python-level ease" without measured user tasks.
7. Set up fair, correctness-checked **C++/Rust native baseline comparisons** once representative CPU/memory constructs run; see [PERFORMANCE.md](PERFORMANCE.md). Do not claim speed parity from a generated object or QEMU boot alone.

**Gate:** every supported construct has a formal example, diagnostics, positive/negative tests and observed native execution through the M1 image.
**Not included:** pretending the language is standard HTML, automatic pointer safety without a proof, full Python compatibility, unplanned dynamic runtime/GC.

### M3 — memory + interrupts

- Receive and validate boot memory map; implement bounded allocation and mapping; preserve kernel reserved regions.
- Define safe default primitives so ordinary user code cannot arbitrarily map physical memory; require explicit privileged operations.
- Add interrupt/exception handlers, logging and controlled fault tests. Do not mistake serial/debugcon output for full device support.
- **Gate:** repeatable mapping/allocation and fault-recovery evidence in QEMU with negative tests for invalid mappings and resource exhaustion.

### M4 — tasks + boundaries

- Define a small task/process model and scheduler; establish calling convention, syscall or message boundary, and ownership rules.
- Enforce user-space vs kernel-space memory isolation; handle crashes/timeouts without corrupting other tasks.
- **Gate:** two independent tasks make observable progress and forbidden user-memory access fails safely in QEMU.

### M5 — minimally useful OS

- Prioritize an input/output terminal and deterministic RAM-backed or embedded filesystem before broad hardware drivers.
- Add a simple user program loader, error reporting and minimal command interaction.
- **Gate:** boot the image, enter a command, read an embedded file, execute a separate program, and report controlled invalid-input behavior.
- **Defer:** browser, Wi-Fi/GPU/USB stacks, multiplayer, installers, gaming support, production-grade disk write operations.

### M6 — carefully scoped physical compatibility

- Build a supported-device list and safe rollback/restore procedure; prefer a spare computer or removable media.
- Never flash firmware, auto-partition disks, or write to production storage as an initial test.
- Capture boot stage, CPU/firmware, input/output observations and failure logs separately from QEMU tests.
- **Gate:** exact tested hardware, controlled repeatable result, and documented limitations. A single device PASS is **not** universal compatibility.

## Always-on workstreams / 모든 단계 공통

| Track | What agents and humans must keep aligned |
| --- | --- |
| **DX / accessibility** | Human-readable examples, beginner quickstart, non-jargon error messages, CI log reproduction |
| **Evidence / quality** | Parser invalid cases, regression map, property/fuzz inputs where justified, QEMU and physical claims kept separate |
| **Safety / security** | Strict input grammar, checked memory ranges, unsafe boundaries, sandboxed QEMU, supply-chain pins and license review |
| **Performance** | Native AOT execution without a mandatory browser/VM; use [PERFORMANCE.md](PERFORMANCE.md) for fair C++/Rust baselines, runtime overhead, code size and regression evidence; no unsupported speed claims |
| **Integration / release** | Reproducible builds, deterministic artifacts, public-safe agent identity, no unapproved Pages/release deployment |

## Risk register and stopping conditions

See [PROJECT_RISKS.md](PROJECT_RISKS.md) for severity, prevention and observable evidence. The most immediate architectural blockers are **boot integration (R1)**, **custom HTML parser semantics (R2)**, and **language usability vs unsafe low-level capabilities (R3)**.

**Do not promote a milestone if:** boot is simulated by a webpage, the artifact cannot be reconstructed, tests are reduced to pass, an unknown parser construct is silently accepted, external source cannot be verified, or real-hardware claims lack observed evidence.

## Using the roadmap in GitHub Issues / for agents

- Use `python3 scripts/roadmap.py --check` to validate the table or `python3 scripts/roadmap.py --json` to get a **read-only structured plan** for an agent. Neither command claims completion or locks a task.
- Open an Issue using the [roadmap task template](../.github/ISSUE_TEMPLATE/roadmap-task.md).
- Use one milestone ID, define observable outcome, dependencies, source/test files and evidence class.
- Agents read [AGENTS.md](../AGENTS.md) → this roadmap → [CODEMAP.md](../CODEMAP.md) → relevant source/tests; check current PR overlaps before writes.
- On completion reference exact revision/PR, tests and unrun checks; update **STATUS**, not this document, to record measured progress.
- For language semantics that change compatibility or memory safety, record an explicit **proposed** decision in [DECISIONS.md](DECISIONS.md) before treating it as confirmed.

## References

- [OSDev Getting Started](https://wiki.osdev.org/Getting_Started) — OS development prerequisites and prioritization
- [OSDev Limine Bare Bones](https://wiki.osdev.org/Limine_Bare_Bones) — native 64-bit first boot path
- [WHATWG HTML parsing](https://html.spec.whatwg.org/multipage/parsing.html) — HTML parser semantics are not a kernel execution model
