# M2-UX7-A — real Python HTML Kernel compiler in browser WebAssembly

**Status:** locally implemented and tested. GitHub PR-head CI, merge and production Pages deployment are separate gates. This is **HTMLK → real x86-target C**, not a complete in-browser ELF/HKEX/ISO compiler.

## Why this is a real compiler rather than a demonstration

A visitor to the static Live page can edit an HTML Kernel Language user program and expand **실제 Python 컴파일러로 브라우저에서 C 생성 (실험)**. Only after the visitor deliberately clicks **실제 HTMLK → C 컴파일**, the page starts a fresh module Web Worker. The Worker loads Pyodide 0.29.5 (Python 3.13.2 WebAssembly) and the **exact six unchanged Python compiler modules** exported from the repository into a private virtual filesystem. It calls the same `compiler.diagnostics.check` and `compiler.htmlk.compile_html(target='user')` as native development. No parallel JavaScript parser or simulated UART print output exists.

The real generated C is returned to a read-only display and can be downloaded as `htmlk-generated-user.c`, with an actual compiler-generated SHA-256 and source hash. Invalid source returns the compiler's true error code, line/column and hint, with no C download. The browser's normal source editor still saves the original HTML file. **Neither action generates a native x86-64 binary or ISO, and clicking the existing virtual CPU button runs only an already-built ISO.**

## Concrete source and trust model

- `scripts/build_public_browser_compiler.py --out-dir build/browser-compiler` copies only `compiler/__init__.py`, `numeric_types.py`, `language.py`, `function_codegen.py`, `htmlk.py`, `diagnostics.py` unchanged. The build publishes a deterministic manifest with SHA-256 and length of every module; the browser Worker verifies every byte **before importing Python**. There is no server-side per-visitor code generation.
- The dynamic Python glue code is a fixed string. HTML source is passed as a **Python global data value** via `py.globals.set`, not interpolated into Python or JavaScript to be executed as source. The real compiler still parses the restricted typed HTMLK language, and the original existing native validation is authoritative.
- HTML input: **1–4096 UTF-8 bytes** (matches ROMFS source-page limit), output: at most 128KiB of C text; per-Python source module at most 100KiB. The browser terminates the Worker after each result/error or a 90-second timeout. Editing/canceling invalidates a stale result and disables any previous C download. A reset also emits the correct change notification.
- The runtime is a **pinned versioned third-party CDN dependency** (`https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`), loaded *only after opt-in*. The compiler Python sources themselves are served on the project origin. This is **not an offline/certified private sandbox**: the CDN must be available and trustworthy. An externally loaded runtime with Worker capabilities could access its in-memory input or use the network if compromised; **do not compile secrets with this experimental feature**. Full self-hosting, subresource pinning/audit, browser memory profiling and cancellation behavior on low-RAM phones are still open.
- No virtual CPU is started by a compile request. The independently tested source → local GCC/binutils → ISO → v86 x86-64 Ring3 guest pipeline remains the reliable runnable path.

## Independent actual Chromium differential evidence

Actual standalone Chromium execution, **not a fake Worker test**, loaded Pyodide WebAssembly and the six exact Python files; Python 3.13.2 in browser and Python 3.14.4 on the Ubuntu PC produced **byte-exact identical x86-64-target C** from the HTML editor's real exported template:

| HTML source | Browser Python→C SHA-256 | Native CPython→C SHA-256 | Outcome |
| --- | --- | --- | --- |
| Default `value="2026"` | `9c27437b87983e3d243946ed9200ed1b8e5c338f56f0990f9e0ac325429732d7` | same | PASS |
| Changed `value="2031"` | `8a28a5d33fdb499a531b0fed58558ae8773df534ba4527167cd55a85e64207e6` | same | PASS |
| Misspelled `<prnit>` | `HK101_TAG`, line 5, column 5, hint `Did you mean <print>?` | same canonical compiler | rejected, C download disabled |

The generated C header is the actual compiler's `/* Generated from HTML Kernel language. x86-64 native C. */`, not a fabricated HTML preview. Independently built real native ISO files from the original and modified HTML have already been verified on actual QEMU and browser v86, including changed guest UART/ROMFS output and six-frame reclamation; **this new browser step itself does not produce those ISO bytes**.

## Reproduce

```sh
python3 -m unittest tests.test_public_browser_compiler -v
node --check site/live/compiler-worker.mjs
node --check site/live/compile.mjs
node --test scripts/test_browser_compiler.mjs
python3 scripts/build_public_browser_compiler.py --out-dir build/browser-compiler
python3 -m unittest tests.test_live_pages -v
```

CI and Pages run these checks, export exact compiler files and manifest to `/html-kernel-os/compiler/`, and require these artifacts exist in the deployed bundle.

## Outstanding M2-UX7 work (Issue #112)

1. Build actual x86-64 machine-code/ELF object from the WebAssembly-generated C with an audited, reasonably sized browser toolchain; validate relocation types, code-page constraints and native ABI.
2. Link to the project's true entry point, produce bounded relocation-free HKEX, and verify the current checksum/format and original-source snapshot without silently weakening user/kernel isolation.
3. Generate a bootable ISO in the browser or introduce a separately audited explicit guest loader. The current static page has **no in-browser ISO builder** and its ROMFS shell has **no user-upload command**.
4. Verify changed browser source yields **changed native executable bytes and changed real guest CPU UART**, with invalid/oversized/stuck and offline/low-RAM negatives. Avoid fake JavaScript output and preserve the original local-build fallback.

This is a meaningful initial browser compiler phase, **not completion of M2-UX7 or M5/M6**.
