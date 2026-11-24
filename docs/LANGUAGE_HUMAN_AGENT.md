# HTML Kernel Language — one syntax for humans and AI agents

**M2-UX1 merged in PR #103; M2-UX2 one-command CLI and reproducible Ring3 ABI merged in PR #106. M2-UX3 app-friendly root aliases passed actual native QEMU and PR #107 exact-head CI/Gitleaks and merged.**
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

## M2-UX3: write a program, not a kernel (merged PR #107)

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

## M2-UX8: optional local integer type annotations (development branch)

```html
<program>
  <main>
    <let name="count" value="3"/>
    <let name="small" value="u32(count)"/>
    <print value="small + 2"/>
    <halt/>
  </main>
</program>
```

Omit only the `type` attribute of `let`. The existing expression type checker
determines the initializer type: a variable, indexed array element, explicit
conversion or typed function result carries its existing integer type.
Literal-only expressions use the existing expression default (u64, or i64
when the expression contains a negative literal under the current rules).
For example, `-1` infers i64 but `0 - 1` uses u64 wrapping; write the
type or an explicit conversion when signedness or width matters.

The inferred type remains fixed for later assignments. Function parameters,
return types and array element types stay explicit. Boolean locals, string
locals, mixed-width coercion, new scoping rules and dynamic attribute names
are NOT added. Ring3 numeric reports remain unsigned. This is initializer
inference, not whole-program type inference or dynamic typing.

The design is informed by [Rust let inference](https://doc.rust-lang.org/reference/statements.html#let-statements)
and [Go short declarations and default constant types](https://go.dev/ref/spec#Short_variable_declarations),
but retains HTMLK's existing fixed-width literal semantics rather than
copying Rust/Go defaults or introducing a new parser. The existing compiler
metadata automatically marks `type` optional; old explicit declarations
generate the same C as equivalent inferred declarations.

Try [inferred-let.html](../examples/inferred-let.html):

```sh
python3 scripts/htmlk.py run examples/inferred-let.html
python3 -m unittest tests.test_inferred_let -v
python3 scripts/test_inferred_let_qemu.py
```

Local native Linux output is 6, 0. Two kernel boots and two Ring3 ISO boots
(with two app executions each) verify actual native output 6, 0 and edited
source 10, 0 with frame reclamation. Explicit/inferred C equivalence and
negative controls cover all three targets. CI, public browser deployment,
physical hardware and external usability measurements are separate gates.

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

## Future M2 language usability work — proposed, NOT shipped

**Packaged IDE extensions and richer diagnostics:** M2-UX5 already supplies
real compiler-backed LSP completion/hints, but syntax highlighting, tag-pair
navigation, workspace indexing and self-installing client extensions are still
not implemented. These should reuse the existing typed compiler rather than
introducing a permissive duplicate language parser.

**True browser-native executable compilation (tracked in Issue #112):** M2-UX7-A
locally implements an actual original-Python-compiler-to-C step inside a
Pyodide Web Worker, with byte-for-byte native CPython C SHA parity, while
M2-UX4's existing verified tools produce the executable ISO **locally**.
The site must NOT claim direct source execution until a browser-side x86
linker produces a NEW HKEX/ISO and real guest CPU output independently changes
with the edited source. JavaScript-computed demo output does not count.
[WebAssembly compiler's actual first-stage evidence](M2_BROWSER_COMPILER_C.md).

**Second native compiler backend — experimental:** M2-UX7-B1 now proves canonical
HTMLK source can generate source-matched TinyCC x86-64 HKEX images and execute
as guarded Ring3 in QEMU, including text, repeated values and full u64. It is
an optional Linux toolchain, **not** TCC running inside the browser. See
[exact provenance and limitations](M2_TCC_NATIVE_PROOF.md).

**Reusable libraries and safe APIs:** versioned modules, small standard
library and explicit permissions/unsafe boundaries remain OPEN, with positive
and negative conformance tests required before shipping.

**Measured human/agent usability:** matched beginner and coding-agent tasks
versus a Python baseline should record time, correction cycles, correctness,
code size and native execution. Real user studies are **NOT RUN**. Do not
claim Python-level ease or C++/Rust performance parity without measurements.

Canonical language semantics: [M2 language contract](M2_LANGUAGE_CONTRACT.md);
design trade-offs: [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md);
observable milestone gates: [ROADMAP.md](ROADMAP.md).

## M2-UX5 editor LSP integration (merged PR #109; actual subprocess protocol + CI PASS)

`scripts/htmlk_lsp.py` exposes bounded standard stdio LSP diagnostics using the existing typed compiler and real grammar tables. Editors receive UTF-16-safe positions, typo hints, attribute/tag completion, hover and the `htmlk.describe` schema for agents. It never builds or runs executable code and does not include a packaged IDE plugin. [Protocol/setup/evidence](M2_LANGUAGE_LSP.md).
