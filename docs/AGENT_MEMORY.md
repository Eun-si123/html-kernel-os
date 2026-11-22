# Agent memory — public-safe durable notes

This is a small repository-level handoff store for future agents. It is not a substitute for current source, [STATUS.md](STATUS.md), CI, GitHub PRs, architecture, decisions, or the live Issue queue.

## What belongs here

- A recurring technical pitfall with independently verified evidence and a canonical source/test link.
- A durable architecture or governance lesson that other contributors would otherwise rediscover.
- A rejected design approach with a concrete reason (not speculation).
- A pointer to an existing decision/status record rather than reprinting the fact.

Keep ephemeral work logs, command output and active tasks in task branch/PR checkpoints, not this document. After an interruption, check live HEAD and working status before trusting a checkpoint.

## Privacy

**Public repository rule:** Never record tokens, keys, private emails/names, private conversations, personal-machine paths, network topology, private repo code, raw sensitive logs, credentials or other identifying context. Use repository-relative paths and links to public, sanitized evidence. If a memory note repeats the only source of truth, replace it with a link.

## Durable notes

### 2026-11-22 — bootability is a separate evidence class

- The initial experiment compiles HTML-like syntax to freestanding C and an x86-64 object. This is not independently bootable. Keep assertions about QEMU/real hardware behind observed boot evidence.
- Current truth: [STATUS.md](STATUS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [VALIDATION.md](VALIDATION.md).
- The static `site/` cannot be treated as a browser-based compiler or proof of a native OS. Preserve separate site-deployment authorization.

### 2026-11-22 — reusable cross-agent governance

- `AGENTS.md` is the common entry point; code navigation, status, decisions, governance, work selection and memory each have distinct owners.
- The feature map directs agents to tests but cannot claim those tests passed, and Issue comments cannot guarantee exclusive locks.
