# M2-UX5 — HTML Kernel Language Server Protocol

**Status:** local development implementation; GitHub PR-head CI and merge are separate gates.

HTML Kernel Language can now expose its **existing typed compiler** to editors and AI coding agents via a bounded LSP stdio server. This is the same compiler that produces native Linux, kernel and Ring3 code. The language server never compiles an executable or runs an HTML program.

## Start the server

From the repository root, configure an LSP-capable editor or client to launch:

```sh
python3 scripts/htmlk_lsp.py
```

Use the editor's standard LSP **stdio** transport and associate the relevant `.html` / `.htmlk` files with that client. To select the native Ring3 target, send `initialize` with:

```json
{"initializationOptions":{"target":"user"}}
```

Other targets are `linux` (default) and `kernel`. This project does **not** yet ship a self-installing VS Code extension, so ordinary VS Code requires an LSP client extension or custom integration. Do not paste JSON directly into the process: LSP messages are framed with `Content-Length` headers.

For one-shot agent checks without an editor:

```sh
python3 scripts/htmlk_check.py examples/human-agent-program.html --target user --json
python3 scripts/htmlk_check.py --describe --json
```

## Supported features

- **Text synchronization:** `didOpen`, `didChange` (full-document only), `didSave`, `didClose`. Each update publishes real compiler diagnostics; closing a document clears them. Obsolete versions are ignored.
- **Accurate errors:** existing `compiler.diagnostics.check` and `compile_html` provide target-specific error codes, messages and hints. Compiler positions are converted from 1-based Unicode columns to zero-based LSP **UTF-16** columns, including emoji preceding errors. Unknown locations are clearly marked document-level instead of pretending to be precise.
- **Completion:** real grammar table names (`CHILDREN`, `ALLOWED`, `REQUIRED`) supply supported tag and attribute names. Cursor prefix matching is lexical only; it does not reimplement syntax validation, promise valid expressions or automatically edit source.
- **Hover:** canonical tag attributes, required attributes and allowed parent tags, without a separate documentation grammar.
- **Agent schema:** `workspace/executeCommand` with `htmlk.describe` returns the exact `--describe --json` schema. This command cannot execute arbitrary shell commands.

The LSP server currently emits at most **one authoritative compiler error per edit**, without multi-error parser recovery, rename, semantic indexing, code refactoring or a packaged IDE plugin. Editors must explicitly connect an LSP client. LSP success is not proof a program booted.

## Boundaries and proof

The server holds at most **16 documents** with **128 KiB UTF-8 bytes** of source each. Incoming LSP frames are limited to **512 KiB**, headers to **4 KiB**. Oversized document text yields a document-level `HK301_BOUNDS` diagnostic without retaining the source; bad/truncated protocol frames terminate the server rather than silently accepting untrusted bytes.

No user-file reads, file creation, compiler invocation via GCC, network access, native code execution, guest boot or second permissive parser occur inside this LSP service. All error semantics come from the original typed compiler, and grammar metadata from its canonical tables.

Run the **real subprocess protocol tests**:

```sh
python3 -m unittest tests.test_htmlk_lsp -v
python3 -m unittest discover -s tests -q
```

The tests send genuine Content-Length-framed JSON-RPC to a separate Python LSP process, verifying initialization/shutdown, document lifecycle, error hints, missing exact location, stale edit ordering, target change, completion/hover, emoji UTF-16 positions, malformed frames and input bounds. This is different from testing a mock handler.

**Not implemented:** standard HTML/DOM execution, browser-hosted native compiler, arbitrary untrusted program sandbox, physical hardware certification, or demonstrated Python-level beginner usability. Actual native execution continues to require the existing Linux/QEMU test paths; M6 physical trials remain separate.
