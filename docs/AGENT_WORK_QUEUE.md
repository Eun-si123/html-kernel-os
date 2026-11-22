# Agent work coordination — lightweight GitHub-native policy

This small repository uses GitHub Issues and PRs as its **live** work queue. This document does not implement a scheduler, agent runner, automatic PR claim, database or exclusive distributed lock.

## Selection and priority

1. Read current Issues, open PRs, branches, CI, and [STATUS.md](STATUS.md) before opening a new task.
2. Prefer verified release/boot blockers, then tested correctness/security defects, then bounded feature improvements, then speculative refactoring.
3. Classify a proposed Issue using optional `priority:p0..p3` and `agent:agent-ready | needs-decision | needs-field-test | blocked | triage` labels when they exist. **Missing labels are untriaged**, not authorization to work.
4. If an Issue has an active PR or another agent's visible claim, coordinate rather than duplicating it.
5. Prefer a dedicated task branch. If several agents work at once, separate source/test ownership and confirm overlapping changed paths again before PR submission.

## Evidence and claim convention

- A descriptive claim comment may record `agent name`, `branch`, `issue number`, `intended files` and bounded expiry, with no private data. It is **advisory**, not an atomic lease.
- Two claims can race. Failure to observe another claim does **not** guarantee exclusive ownership.
- PR body should capture exact source SHA, goal, regression tests, CI status, unrun QEMU/hardware tests, and rollback.
- Follow-up after interruption must inspect the live checkout; a saved checkpoint is not proof work has stopped.
- No commit or Issue churn for scheduling quotas alone. A correct **no change** decision is valid if no justified task is ready.

## Readiness vocabulary

- `agent-ready`: bounded, approved implementation with relevant failure tests; not self-authorization.
- `needs-decision`: meaningful conflicting semantics requiring owner choice.
- `needs-field-test`: code may exist but real QEMU/physical validation remains.
- `blocked`: specific missing prerequisite, pending CI or dependency.
- `triage`: scope/evidence incomplete.

Queue state cannot weaken CI, source review, identity privacy, branch protections or release/deployment controls.
