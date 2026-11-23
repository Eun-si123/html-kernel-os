# HTML Kernel OS — documentation hub

Start with [AGENTS.md](../AGENTS.md) for AI collaborators and [README.md](../README.md) for humans. This small repository borrows **the structure**, not unrelated product-specific rules, from TeamForge and BetterNet-App.

| Question | Canonical document |
| --- | --- |
| What is actually implemented and tested? | [STATUS.md](STATUS.md) |
| **What to build next, with clear pass/fail gates?** | [ROADMAP.md](ROADMAP.md) |
| How can an HTML-based language be easy like Python? | [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) |
| Which M2 language features are actually implemented and what are the limits? | [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md) |
| How can we reach C++/Rust-class native speed? | [PERFORMANCE.md](PERFORMANCE.md) |
| Which assumptions, hazards and unknowns matter? | [PROJECT_RISKS.md](PROJECT_RISKS.md) |
| Which test/evidence class is required? | [VALIDATION.md](VALIDATION.md) |
| How do two distinct Ring3 CR3s survive a task CPU fault? | [M4_FAULT_ISOLATION.md](M4_FAULT_ISOLATION.md) |
| How does the opt-in M5-A real embedded read-only filesystem work? | [M5_ROMFS.md](M5_ROMFS.md) |
| How does real QEMU UART command input read embedded files? | [M5_SERIAL_CONSOLE.md](M5_SERIAL_CONSOLE.md) |
| How does M5-C1 ROMFS user code run in real CPL3? | [M5_USER_LOADER.md](M5_USER_LOADER.md) |
| How can I enter `run /apps/hello.hke` into a real guest UART shell? | [M5_SHELL.md](M5_SHELL.md) |
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
