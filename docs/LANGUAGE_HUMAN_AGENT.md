# HTML Kernel Language — one syntax for humans and AI agents

**Implementation phase: M2-UX1 / local feature branch.**
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
