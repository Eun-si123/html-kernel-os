# HTML Kernel Language — one syntax for humans and AI agents

**M2-UX1 merged in PR #103; M2-UX2 one-command CLI and reproducible Ring3 ABI merged in PR #106. M2-UX3 app-friendly root aliases have local test evidence and PR-head CI/merge pending.**
A useful programming language should be understandable from its source,
provide actionable feedback to a beginner, and give an agent a **stable
machine-readable contract**. A browser-looking demo or a larger list of tags
is not enough. This phase adds only a thin development interface around the
existing checked compiler: no duplicated grammar, no relaxed validation, no
new unsafe runtime path and no invented "standard HTML execution".

## A first program

The same [example](../examples/human-agent-hello.html) is accepted by
**three** existing compiler targets: Linux process, x86-64 kernel, and a
read-only Ring3 HKEX program. Its numeric output is 3, 3, 3, 4294967296.

```html
<kernel arch="x86_64">
  <onboot>
    <let name="count" type="u64" value="3"/>
    <repeat times="3">
      <print value="count"/>
    </repeat>
    <print value="4294967296"/>
    <halt/>
  </onboot>
</kernel>
```

This is **HTML-shaped language syntax**, NOT standard browser HTML. The
compiler interprets tags as typed instructions, lowers to freestanding C,
and uses GCC/native linking to obtain real CPU instructions. The
`<kernel><onboot>` naming currently also applies to Linux and Ring3 targets
for grammar reuse; human-readable aliases and simpler entrypoints are a
separate, not-yet-implemented design question. Nor do tags alone remove
systems-programming complexity.

## M2-UX3: write a program, not a kernel (local development)

Newcomers should not need `<kernel><onboot>` to write a normal Linux
program or an unprivileged Ring3 user app. The same parser now accepts
**optional nonkernel-only aliases** `<program>` (root) and `<main>`
(entrypoint) with the same typed AST, statements and expression rules.

```html
<program>
  <main>
    <let name="count" type="u64" value="3"/>
    <repeat times="3"><print value="count"/></repeat>
    <print value="4294967296"/>
    <halt/>
  </main>
</program>
```

The full [real runnable example](../examples/human-agent-program.html)
also defines a typed `double(x:u64)` function sibling to `<main>`.
It prints `6` three times and `4294967296` once. The original
`<kernel arch="x86_64"><onboot>...</onboot></kernel>` remains accepted
on **all three** target backends, preserving all existing code. For Linux
and Ring3, replacing only the outer aliases yields **byte-for-byte
identical generated C** (same checked typed AST), proved by tests.
For the native kernel backend, `<program>` explicitly **fails before
code generation**, so a user program cannot silently become privileged
code. Mixed `<program><onboot>` / `<kernel><main>`, malformed closing
tags, extra attributes, bad types, oversized repeat bounds and root
architecture are rejected with the same existing diagnostics.

```sh
python3 scripts/htmlk.py check examples/human-agent-program.html --target user --json
python3 scripts/htmlk.py run examples/human-agent-program.html
python3 scripts/htmlk.py build examples/human-agent-program.html --target user --out build/my-app.hke
python3 scripts/test_htmlk_program_main_qemu.py
```

The native QEMU acceptance suite builds a **real** ROMFS HKEX from this
new alias-form HTML, runs it twice in actual CPL3 with six-frame reclamation,
then changes source `count=3` to `count=5`, builds a *different ISO* and
observes a true CPU UART change from three `6` reports to three `10`
reports. Passing grammar tests alone does not establish that real guest
execution happened. The `<program>` and `<main>` tags do **not** mean a
browser interprets ordinary HTML as executable machine code; they are
source-language forms compiled through the same native toolchain.

## Human-first validation

```sh
python3 scripts/htmlk_check.py examples/human-agent-hello.html
python3 scripts/htmlk_check.py examples/human-agent-hello.html --target user
python3 scripts/htmlk_check.py --describe
```

`htmlk_check.py` validates **using the existing real compiler and target
semantic rules**, keeping generated C in memory and writing **no artifact**.
It emits a successful concise status on stdout, or a nonzero status with
file, 1-based line/column where available, source line, caret, diagnostic
code and suggestion. Example: `<prnit>` suggests `<print>`.
No source position is invented for errors where the underlying compiler
does not supply one. Target choice matters: `--target user` has bounded
report and final-print constraints; `--target linux` is the default.

The native Linux compiler and the real Ring3 builder remain **independent
commands** (not simulated by the checker):

```sh
python3 compiler/htmlk.py examples/human-agent-hello.html --target linux --out build/first.c
gcc -std=c11 -O2 build/first.c -o build/first
./build/first
python3 scripts/build_html_user_image.py --source examples/human-agent-hello.html --out build/first.hke
python3 scripts/test_htmlk_human_agent_boot.py
```

The real native QEMU integration test uses a separately compiled HKEX in
ROMFS, sends two guest COM1 `run` requests, observes six `3` reports, two
4294967296 reports, bounded user frame reclamation, then independently
mutates the source from count=3 to count=5 and proves a changed ISO and
changed actual CPU output. **A passing checker is not a boot test.**

## Agent-first, versioned diagnostic format

```sh
python3 scripts/htmlk_check.py --describe --json
python3 scripts/htmlk_check.py examples/human-agent-hello.html --target user --json
python3 scripts/htmlk_check.py - --target linux --json < examples/human-agent-hello.html
```

The `--describe --json` response is generated from the actual grammar
tables `CHILDREN`, `ALLOWED` and `REQUIRED`: accepted tags, parent
contexts, required and allowed attributes, integer types, limits and
target names. Other semantic constraints **still require a real compile**;
this schema is discoverability, **not** an exhaustive language-server
definition or a promise that any tag arrangement is valid.

The checker emits **one JSON object on stdout**; failures exit 1 and have
`ok: false`, `schema_version: 1`, `file`, `target`,
`diagnostics: [{severity, code, message, line, column, hint}]`,
`source_sha256`, and `generated_c_sha256: null`. On success the
`diagnostics` array is empty and both SHA-256 fields identify the checked
source and in-memory generated C. `line` and `column` are **null** when
the original compiler does not report a position. The schema is intentionally
small, deterministic and free from prompts, injected code execution,
network calls and private environment values. It is not a language model
control protocol or a tool that edits or executes input by itself.

Agents should: **discover → generate a small file → check → read errors →
edit → check again → build/run in a separately chosen trusted environment**.
Do not generate hundreds of variants until one compiles; do not treat an
OK check as proof the guest booted or that arbitrary code is safe.

## Safety and honest boundaries

- One authoritative typed compiler: `compiler/language.py` and
  `compiler/htmlk.py`; the checker only calls `compile_html`.
- User source is bounded to 128 KiB, input must be UTF-8; checker rejects
  symlink inputs and never writes executable files.
- Current syntax is not browser DOM/JavaScript/CSS, Python compatibility,
  or a mature general-purpose language. Error suggestions do not silently
  fix or execute code.
- QEMU, Chromium v86, compiler object, Linux process, and real hardware
  have **different acceptance gates**. No real-PC or arbitrary-input
  Ring3-sandbox assurance follows from these tests.
- The schema is stable **v1** for this CLI, but the project has not
  published cross-version language compatibility or external beginner
  usability results. Existing M2 grammar and native ABI remain unchanged.

## M2-UX2: one command for real native programs (local, not yet merged)

The compiler can now be used from a single, explicit developer entrypoint.
This is **not** a second parser or an interpreter; all program semantics and
native output come from the existing typed language compiler.

```sh
python3 scripts/htmlk.py describe --json
python3 scripts/htmlk.py check examples/human-agent-hello.html --target user --json
python3 scripts/htmlk.py run examples/human-agent-hello.html
python3 scripts/htmlk.py run examples/human-agent-hello.html --json
python3 scripts/htmlk.py build examples/human-agent-hello.html --target linux --out build/first
python3 scripts/htmlk.py build examples/human-agent-hello.html --target user --out build/first.hke
```

The `run` command compiles the real source to native C → ELF via GCC in a
private temporary directory, runs that generated **Linux process** with
closed stdin, a bounded 10-second timeout and maximum 16-KiB captured output;
then removes the generated temporary files. Standard output is native CPU
output. `--json` reports code-generated SHA-256, actual stdout/stderr and
exit code. This is **not an operating-system sandbox**; do not use as an
untrusted-code execution service. `run` does not boot QEMU or execute
privileged kernel code. The kernel target remains handled separately by the
real ISO builder. No root permission, host system disk configuration or
external network access is required for the CLI itself.

The `build --target linux|user` command emits a real executable ELF or a
checked relocation-free HKEX binary, respectively. Existing destinations
are refused by default; `--force` allows explicit replacement, but a
symlink destination is never replaced. The output is committed only after
full successful compilation via a temporary staging file, using an atomic
**no-clobber hard link** for default creation; a concurrent agent writing the
same path gets a controlled error rather than losing its output. A real
concurrent-process test checks that only one writer succeeds. Invalid UTF-8,
large/symlink sources and invalid HTMLK syntax are rejected before output
creation. `check` and `describe` delegate to the earlier checker rather than
implementing a competing grammar. AI agents can use stable `--json` results.

**Important Ring3 ABI distinction:** the prior ROMFS `--user-app-image` path
retains the **legacy** numeric output limit and one-report contract. A new
opt-in ISO build argument `--user-app-html-proof SOURCE.html` works alongside
`--user-app-image image.hke` only: the builder **recompiles a stable snapshot
of SOURCE.html** via the original compiler and requires byte-for-byte
identity with the supplied HKEX before enabling the HTML-only bounded
u64/text/multi-report/exit-status ABI. A missing proof is NEVER interpreted
as permission; mismatched, tampered, symlink, oversized or unsupported proof
inputs fail before an ISO is published. This is a local reproducibility
assertion, **not cryptographic authentication** of third-party binaries or a
security boundary for untrusted programs.

```sh
python3 scripts/build_boot.py --exception-idt --tss-ist \
  --romfs-run-console --user-fault-recover \
  --user-app-image build/first.hke \
  --user-app-html-proof examples/human-agent-hello.html \
  --out build/first.iso
# Boot the ISO via QEMU or the existing browser emulator (not the Linux run command)
python3 scripts/test_htmlk_cli_qemu.py
```

The real QEMU regression boots the exact CLI-built HKEX twice, reclaims
six user frames after each independent run, mutates the HTML from `3` to
`5` and verifies a different HKEX/ISO and changed CPU UART output. A
**negative native boot** proves a prebuilt image WITHOUT proof still fails
under the old syscall limit with a recoverable task error. Additional
fail-closed tests reject wrong source, corrupt image, symlink proof and
mutually incompatible build options. Existing M2/M5 native regressions
remain mandatory; a successful Linux run is not a QEMU boot.

## Next M2 language usability phases — proposed, NOT shipped

**M2-UX2:** editor integration with syntax highlighting, matching tags,
source mapped errors and completion. Browser source editing only counts as
"real HTML execution" when user edits yield a *new native artifact* and a
different verified CPU result; presenting JS-calculated output is not enough.

**M2-UX3:** tagged standard library/modules, clearer reusable I/O functions,
explicit permissions and safe APIs, a stable versioned grammar plus an
automated positive/negative conformance corpus. Avoid adding unrelated
parsers or a new runtime without evidence of improved usability.

**M2-UX4:** measured beginner/agent evaluations (time to correct program,
edits per task, error recovery, generated native execution) versus
equivalent Python and existing HTMLK syntax. Real user studies are
**NOT RUN**. Do not assert this language is already easier than Python.

Canonical language semantics: [M2 language contract](M2_LANGUAGE_CONTRACT.md);
design trade-offs: [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md);
observable milestone gates: [ROADMAP.md](ROADMAP.md).
