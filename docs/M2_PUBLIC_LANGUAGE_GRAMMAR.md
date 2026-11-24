# M2-UX6 — compiler-generated, public language reference

**Product goal:** let both a human beginner and a coding agent see the same actual supported HTML Kernel Language grammar while editing on the separate GitHub Pages Live Lab.

## Source of truth

```sh
python3 scripts/build_public_language_grammar.py --out build/htmlk-language.json
python3 scripts/htmlk_check.py --describe --json
```

The public JSON is created at build time directly from the **existing authoritative** `compiler.diagnostics.describe()` using `compiler/language.py` tag, parent, required/allowed attribute and scalar type declarations. It is **not** another JavaScript language implementation. The JSON includes SHA-256 of `compiler/language.py` and `compiler/htmlk.py` for reproducibility/consistency, **not a third-party signature or executable attestation**. The metadata is limited to 16KiB and written only into an existing directory (symlink destinations rejected).

The effective parent list includes `main` for statements accepted inside the app-friendly `<program><main>` aliases, in addition to the canonical legacy `onboot` parent. The compiler still canonicalizes aliases into the same typed AST: this metadata change **does not add a second parse or relax actual code generation**. The source examples and native Linux/Ring3 program outputs remain the same.

## Website and agent workflow

The GitHub Pages build creates and publishes a read-only `/html-kernel-os/htmlk-language.json` alongside the existing browser VM and editor. A [Live Lab](https://eun-si123.github.io/html-kernel-os/live/) visitor can expand **지원되는 HTML Kernel 언어 태그·속성 보기**, search by tag/attribute/allowed-parent and see the actual compiler-derived mandatory attributes. The list is rendered using safe `textContent` DOM nodes, never `innerHTML` or injected tag rendering. It loads only when the user opens the reference, so real VM execution is not held hostage by a metadata request.

AI agents can fetch the same static JSON without scraping Markdown; `schema_version=1`, `tags`, `types`, `limits` and per-tag parent/attribute fields have a stable shape matching the existing CLI. **Those lists are not a full proof of semantic validity**: compiler target rules, expression types, bounds, source text and native output still require actual `scripts/htmlk_check.py --target ...` and native QEMU/guest execution when boot behavior matters. GitHub Pages never directly compiles edited HTML.

## Evidence and safety

```sh
python3 -m unittest tests.test_public_language_grammar -v
node --test scripts/test_live_grammar.mjs
python3 -m unittest tests.test_live_pages -v
```

Tests require deterministic compiler-derived JSON with exact canonical tags/attributes/required fields and SHA-256, demonstrate real equivalent `<program><main>` native output, reject symlink/missing-directory builds, and verify client search, tampered or oversized static metadata, safe display data and no browser-side interpretation of untrusted code. CI and Pages independently generate metadata from the same Python compiler; the site artifact checks both the JSON and read-only JS module are present.

**Boundaries:** this is language discoverability, **not** a browser-resident compiler, LSP IDE extension, semantic auto-fix, arbitrary-code security sandbox or M6 physical hardware test. It is usable with the M2-UX5 LSP, but does not require that service to run on the public site. Exact PR-head CI, merge and public deployment remain separate acceptance gates.
