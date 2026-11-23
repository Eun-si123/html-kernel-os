# HTML Kernel OS — development roadmap / 개발 로드맵

**Audience:** human contributors, beginner programmers, coding agents, reviewers.
**Project goal:** express increasingly capable **native OS/kernel logic** in an HTML-like systems language, while retaining a reproducible boot chain and honest execution evidence.

> **한국어 요약:** `kernel.html → C → x86-64 커널 이미지 → 실제 QEMU BIOS 부팅`이 로컬 및 GitHub CI에서 검증됐어(M1). M2의 핵심 변수·타입·제어 흐름·함수·배열을 QEMU에서 검증했고, **M3의 제한된 메모리·예외 처리 QEMU 완료 기준도 통과했어.** 다음 목표는 **M4 작업·보호**이고, 이후 M5 최소 사용자 환경과 M6 실기기 검증으로 이어져. 실제 커널 부팅은 첫 성취로 검증됐고, **브라우저 체험도 한 Chromium 환경에서 동작을 확인**했어. Linux 사용자 프로그램의 최초 실행 경로는 구현·CI 검증됐고, 실제 PC 부팅은 추후 목표야. 브라우저 UI 시뮬레이션은 커널 부팅 증거가 아니야. 구체적인 병행 계획은 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)를 참고해.

## How to read this / 읽는 방법

- **Milestone ID `M0`…`M6`** is stable: use it in Issues, PRs, commits, checkpoints, and agent reports.
- **Acceptance gate** is the only definition of completion. A document, stub, generated object, or passing unit test alone cannot satisfy a boot/hardware gate.
- **Dependencies** are prerequisites, not permission to claim they passed. Implementation can be explored in parallel on separate branches; completing a later milestone still requires its prerequisites.
- **Current truth** lives in [STATUS.md](STATUS.md), actual source/tests, and GitHub CI. The roadmap describes goals and requirements; it is **not** an implementation scoreboard.
- Work on the **nearest unmet, unblocked milestone**, except for a confirmed high-priority correctness/security/privacy issue. Separate exploratory design from verified implementation.
- Each task needs a measurable outcome, a negative test/failure case, and explicit NOT RUN evidence classes. See [VALIDATION.md](VALIDATION.md).

## Founder interview Q1–Q20 and parallel delivery plan

The completed [founder interview](INTERVIEW_DECISIONS.md) confirms **D + E** success criteria: prove actual source-derived kernel boot first, then expand real HTML-language kernel functions and practical use; adjust later gates only with observed evidence. The [implementation plan](IMPLEMENTATION_PLAN.md) maps work into **P0–P5 execution slices**: language-core reliability, M1 boot, minimal Linux userspace target, language usability, browser/Windows demos, and existing M3–M6 kernel capabilities. **P-slices are planning workstreams, not replacement M-milestones or shipped features.**

M1 QEMU BIOS boot and one Chromium browser boot are verified; the M2 **core boot-integrated programming subset is verified** (see STATUS), with M3 now the next acceptance gate; Linux-native compilation is now verified for the existing language subset; Linux OS/distribution support remains a separate, unimplemented goal. Continue developing reusable compiler semantics and target-specific execution support. Any website/browser UI simulation must be labeled separately from real boot emulation.

## Milestone overview

| ID | Goal | Depends on | Acceptance gate / 완료 기준 |
| --- | --- | --- | --- |
| **M0** | HTML → freestanding native object | — | Parser tests + generated C + x86-64 object from the same source (baseline achieved; see STATUS) |
| **M1** | **Boot HTML-derived code in QEMU** | M0 | Reproducible x86-64 boot image; headless QEMU emits exact expected message from `kernel.html`; bounded automated PASS and negative FAIL |
| **M2** | Readable core programming language | M0; M1 for OS-integrated gate (design work can start earlier) | Variables, types, arithmetic, branches, loops, functions + safe diagnostics; representative source examples compile and run in the boot environment |
| **M3** | Memory and fault handling | M1, relevant M2 primitives | Memory map, bounded physical allocator and virtual mapping, deliberate fault evidence, repeatable QEMU tests |
| **M4 — NEXT** | Scheduling and privilege separation | M3 | Two distinct tasks execute deterministically; user/kernel isolation and bad-access rejection are demonstrable |
| **M5** | Minimal useful operating environment | M4 | Console input, small read-only initial filesystem, independent user program execution and reproducible tests |
| **M6** | Reliability + carefully scoped real-hardware trial | M5 | Recoverable, read-only-first physical test on an explicitly supported machine with reproducible observations; no untested hardware-wide support claim |

### M0 — source-to-object baseline (already evidenced)

- Current prototype supports `<kernel>`, `<onboot>`, `<print>`, `<halt/>` only; output targets **QEMU debugcon port 0xE9**, not a display driver.
- Acceptance: parse valid input; reject invalid structures; compile freestanding C with `-Werror`; verify the object format.
- **Does not prove:** bootloader linkage, QEMU execution, actual physical I/O, an OS, or general Python-level language features.
- References: [CODEMAP](../CODEMAP.md), [STATUS](STATUS.md).

### M1 — first *real* boot (verified; see STATUS/CI)

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

**Partial implementation:** u32/u64 arithmetic, scoped typed functions, if/else and bounded repeat are CI-verified with QEMU/Linux and a Chromium browser boot. Signed i32/i64, explicit width/signedness conversions, unsigned bitwise/shifts and repeat break/continue have **real Linux + QEMU, PR/main CI and Chromium browser boot PASS** (PR #29). Independent 464-case Python-vs-GCC (-O0/-O3 UBSan) arithmetic differential test passes locally. See [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md). Bounded condition-driven `while` and integer division/remainder are merged (#35/#36); checked local arrays and five representative native learner tasks are merged and CI-verified (PR #37, main run `45092578504`). The M2 core gate is met for its **documented supported subset**, with real QEMU/Linux positive and negative tests. This is **not** the full general-purpose language goal. Structs, modular compilation, memory-safe low-level APIs, external novice evaluation and comparative performance measurements remain OPEN.

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

**Experimental first slice (PR #38):** an opt-in, checksum-pinned Limine memory-map/HHDM handoff and 16 x 4KiB bounded USABLE physical-page pool have passed an initial BIOS QEMU and GCC UBSan run. Source-change and malformed-map negative controls distinguish a real boot from synthetic output; see [M3_MEMORY_BOOTSTRAP.md](M3_MEMORY_BOOTSTRAP.md). An additional **opt-in native Limine framebuffer console** now passes real QEMU pixel readback and an independently verified VGA screenshot (PR #39, CI verified); see [M3_FRAMEBUFFER_CONSOLE.md](M3_FRAMEBUFFER_CONSOLE.md). An additional opt-in 256-entry x86-64 **CPU exception IDT** now catches real #DE/#UD/#GP/#PF in QEMU, reports RIP/error/CR2 and halts instead of triple-faulting (PR #40, merged and CI verified). See [M3_EXCEPTION_IDT.md](M3_EXCEPTION_IDT.md). A **single private 4KiB supervisor-only virtual mapping** now passes real QEMU CR3 activation, HHDM alias readback, `invlpg` revocation, restored CR3, source mutation and a genuine #PF after unmap (PR #41, merged and CI verified, opt-in experiment). See [M3_PRIVATE_PAGING.md](M3_PRIVATE_PAGING.md). An opt-in **one-shot recoverable #PF** now allocates a zeroed owned frame in the actual CPU IDT handler and returns with `iretq`, while rejecting all unarmed faults (PR #44, merged and CI verified). Full 16-frame owner/reuse/exhaustion checks accompany it; see [M3_FAULT_RECOVERY.md](M3_FAULT_RECOVERY.md). An opt-in **64-bit TSS with separate IST1/#DF and IST2/#PF stacks** also passes genuine BIOS QEMU fault delivery, plus combined one-shot recovery and native video (PR #46, merged and CI verified). See [M3_TSS_IST.md](M3_TSS_IST.md). An additional **bounded three-page mapping** now runs three repeated owner-reclaim cycles with real CPU virtual/physical aliases and negative revoked-page #PF evidence (PR #47, final CI validating). See [M3_MULTIPAGE.md](M3_MULTIPAGE.md). **M3 bounded QEMU acceptance gate PASSED on PR #47 push/PR CI** (`45105414876`/`45105421245` at `7bfa7a1`), including repeatable map/claim/unmap/release, true CPU #PF recovery/rejection, TSS/IST and negative controls. **M4 is NEXT.** General-purpose VM heap, broad page fault policies, hardware IRQs/timers, SMP, lifetime ownership across tasks and physical hardware remain unimplemented; these are *not* inferred from the M3 milestone gate.

- Receive and validate boot memory map; implement bounded allocation and mapping; preserve kernel reserved regions.
- Define safe default primitives so ordinary user code cannot arbitrarily map physical memory; require explicit privileged operations.
- Add interrupt/exception handlers, logging and controlled fault tests. Do not mistake serial/debugcon output for full device support.
- **Gate:** repeatable mapping/allocation and fault-recovery evidence in QEMU with negative tests for invalid mappings and resource exhaustion.

### M4 — tasks + boundaries

**Implementation slices:** M4-A separate ring-0 kernel task stacks and explicit cooperative context switching; M4-B interrupt/time accounting and deterministic bounded scheduling; M4-C ring-3 CPL transitions, TSS.RSP0 and a minimal syscall boundary; M4-D per-task memory access permission checks, fault cleanup and regression tests. Only M4-D plus the independent-task runtime gate can complete this milestone. M4-A is a separate opt-in QEMU experiment: see [M4 task proof](M4_TASKS.md). M4-B1 is also opt-in and proves real IRQ0/PIT timer pacing with legacy PIC only under QEMU no-APIC; [timer proof](M4_PIT_IRQ.md). **M4-B2** is an independent opt-in QEMU x2APIC local timer proof of genuine interrupt-driven preemption of two never-yielding ring-0 tasks, with full GPR IRQ stack save/restore, source-mutation and masked-timer negative controls; [B2 validation](M4_X2APIC_PREEMPT.md). **M4-C1** separately boots true CPL3 code on isolated user pages, executes INT 0x80 on a dedicated TSS.RSP0 stack, resumes user code via IRET and validates real CPU #GP/#PF denial of kernel read, user RO-code write and privileged I/O; [C1 proof](M4_RING3_C1.md). **The earlier M4-A/B2 and C1 experiments alone do not provide fault-surviving concurrent user tasks.** **M4-C2** now proves two distinct CPL3 user task CR3 roots with real CPU #PF/#GP offender retirement, survivor execution, six-frame-per-task reclamation and no ownership leak in native QEMU; see [C2 fault isolation](M4_FAULT_ISOLATION.md). C2 is a sequential opt-in probe, not combined with M4-B2 timer preemption. **M4-D** concurrent user-mode scheduling with TSS.RSP0, IRQ state, CR3 and stricter syscall boundaries remains NEXT. Full M4 milestone remains OPEN.

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
