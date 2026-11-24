# HTML Kernel OS — documentation hub

Start with [AGENTS.md](../AGENTS.md) for AI collaborators and [README.md](../README.md) for humans. This small repository borrows **the structure**, not unrelated product-specific rules, from TeamForge and BetterNet-App.

| Question | Canonical document |
| --- | --- |
| What is actually implemented and tested? | [STATUS.md](STATUS.md) |
| **What to build next, with clear pass/fail gates?** | [ROADMAP.md](ROADMAP.md) |
| How can an HTML-based language be easy like Python? | [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) |
| How can people and coding agents check, build and run native HTMLK programs, with verified ABI? | [LANGUAGE_HUMAN_AGENT.md](LANGUAGE_HUMAN_AGENT.md) |
| How to write an app using `<program><main>` instead of `<kernel><onboot>`? | [LANGUAGE_HUMAN_AGENT.md](LANGUAGE_HUMAN_AGENT.md) |
| How can I write HTML in the browser, download, compile, and boot a real ISO? | [M2_WEB_EDITOR.md](M2_WEB_EDITOR.md) |
| Which M2 language features are actually implemented and what are the limits? | [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md) |
| How can we reach C++/Rust-class native speed? | [PERFORMANCE.md](PERFORMANCE.md) |
| Which assumptions, hazards and unknowns matter? | [PROJECT_RISKS.md](PROJECT_RISKS.md) |
| Which test/evidence class is required? | [VALIDATION.md](VALIDATION.md) |
| How do two distinct Ring3 CR3s survive a task CPU fault? | [M4_FAULT_ISOLATION.md](M4_FAULT_ISOLATION.md) |
| How does the opt-in M5-A real embedded read-only filesystem work? | [M5_ROMFS.md](M5_ROMFS.md) |
| How does real QEMU UART command input read embedded files? | [M5_SERIAL_CONSOLE.md](M5_SERIAL_CONSOLE.md) |
| How do HTML apps print repeatedly while keeping a kernel-enforced syscall budget? | [M5_HTML_MULTI_REPORT.md](M5_HTML_MULTI_REPORT.md) |
| How does a Ring3 HTML app safely pass printable text to the UART shell? | [M5_HTML_USER_TEXT.md](M5_HTML_USER_TEXT.md) |
| Can the same HTML-like language compile into a separate Ring3 user executable? | [M5_HTML_USER_PROGRAM.md](M5_HTML_USER_PROGRAM.md) |
| How does M5-C1 ROMFS user code run in real CPL3? | [M5_USER_LOADER.md](M5_USER_LOADER.md) |
| How can a real UART command launch a separate Ring3 program and return to shell? | [M5_INTERACTIVE_RUN.md](M5_INTERACTIVE_RUN.md) |
| How do actual CPL3 #GP/#PF/#UD exceptions terminate just the task and recover the prompt? | [M5_USER_FAULT_RECOVERY.md](M5_USER_FAULT_RECOVERY.md) |
| How does compilation work, and what does not work? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What has been decided versus proposed? | [DECISIONS.md](DECISIONS.md) |
| What did the founder answer in interviews 1–20, including deferred choices? | [INTERVIEW_DECISIONS.md](INTERVIEW_DECISIONS.md) |
| What to implement next across kernel/Linux/browser tracks? | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| What should agents do before GitHub changes? | [AGENT_GOVERNANCE.md](AGENT_GOVERNANCE.md) |
| How to avoid duplicate / conflicting agent work? | [AGENT_WORK_QUEUE.md](AGENT_WORK_QUEUE.md) |
| How are AI commits credited safely? | [AGENT_COMMIT_IDENTITY.md](AGENT_COMMIT_IDENTITY.md) |
| Where are durable lessons kept? | [AGENT_MEMORY.md](AGENT_MEMORY.md) |
| Which files own which implementation? | [../CODEMAP.md](../CODEMAP.md) |
| How are regressions routed across agents? | [../agent-evals/README.md](../agent-evals/README.md) |

## One authoritative owner per fact

- Live code and tests define behavior; exact-head CI defines what automation really executed.
- [STATUS.md](STATUS.md) tracks verified capabilities, not planned milestones.
- [ARCHITECTURE.md](ARCHITECTURE.md) explains technical design and limitations.
- [DECISIONS.md](DECISIONS.md) records user decisions and proposals without inventing approval.
- [VALIDATION.md](VALIDATION.md) defines what proof is required for source, compile, QEMU and physical-machine claims.
- [AGENT_MEMORY.md](AGENT_MEMORY.md) stores only reusable cross-session lessons not already owned elsewhere.
- GitHub Issues and PRs own the live work backlog and review discussion.

When a feature changes, update the **one authoritative** owner, then fix any contradictory status references. Historical snapshots must stay historical. Run `python3 scripts/check_docs.py` and `python3 scripts/roadmap.py --check` after roadmap/documentation edits. Agents can request a read-only plan via `python3 scripts/roadmap.py --json`.

- [M5-E2 real Ring3 x2APIC timeout and UART shell survival](M5_USER_TIMEOUT.md).

- [M5-E3 mixed real QEMU user-process lifecycle and reclamation stress test](M5_PROCESS_LIFECYCLE_STRESS.md).

- [M5-E3-C guarded malformed Ring3 syscall frame process-only abort](M5_USER_SYSCALL_FRAME.md).

- [M5-E3 guarded last-instruction Ring3 INT80 EOF and safe terminal exit](M5_USER_SYSCALL_EOF.md).
- [M5-E3-D independently owned Ring3 x2APIC malformed user stack IRQ recovery](M5_USER_BAD_IRQ.md).

- [M5-F4 HTML Ring3 user program exit status and live UART result](M5_HTML_EXIT_STATUS.md).

- [M5-F5 full unsigned u64 from HTML user code to native COM1](M5_HTML_U64_OUTPUT.md).

- [M5-E3-E actual CPL3 UD2 after corrupted RSP and exact trusted CPU-frame recovery](M5_USER_BAD_UD.md).

- [M5-E3-F actual CPL3 divide by zero with bad RSP, shared exact CPU ownership proof](M5_USER_BAD_DE.md).

- [M5 Web Live: dedicated GitHub Pages x86-64 CPU boot of HTML-compiled Ring3 app](M5_WEB_LIVE.md).

- [M5-E3-G genuine CPU #GP after poisoned user stack and distinct 48-byte error-word proof](M5_USER_BAD_GP.md).

- [M5-E3-H real poisoned Ring3 RSP #PF5/#PF7 IST2 provenance and owner recovery](M5_USER_BAD_PF.md).

- [M5-E3-I actual Ring3 #DB/#BP trap-class CPU frame after corrupted user RSP](M5_USER_BAD_TRAP.md).

- [M5 Web-Live C locally edited HTML compiled to custom native ISO, imported to browser](M5_WEB_LOCAL_ISO.md).
