# M2-UX10-A — explicit source-library composition

**Development branch:** reproducible source bundling, not a general module
system or a native-code backend. The first step lets humans and agents share
pure functions in separate files while using the same compiler for all targets.

```sh
mkdir -p build
python3 scripts/htmlk.py bundle examples/libraries-app.html --library examples/libraries/math.html --target user --out build/library-app.html
python3 scripts/htmlk.py run build/library-app.html
python3 scripts/htmlk.py build build/library-app.html --target user --out build/library-app.hke
```

Expected Linux output: `25`. The library contains ordinary typed HTMLK
functions, not a new language. The application uses `sum_squares(3, 4)`.
Repeat `--library` for explicitly selected files (maximum eight). Each
library is a function fragment, not a separate entrypoint. Functions can
refer to each other across selected files. All names share the existing
function namespace; duplicate names, cycles, invalid types and violations of
the existing aggregate compiler bounds are rejected.

The command does not automatically discover files from source, follow URLs,
resolve import paths, access a package registry, or execute a program. It
uses the canonical HTMLK parser to locate the root and validate fragment
structure, then validates the exact self-contained UTF-8 output with the
existing typed compiler for the chosen target. It refuses stdin, existing
output and symlink inputs/outputs (using the CLI's regular-file reader and
atomic no-clobber publication). `--json` returns the exact output SHA-256,
target and library count. It does not claim a secure arbitrary-source sandbox.

A merged HTMLK source is an ordinary program, compatible with native Linux,
Ring3 HKEX, kernel ISO (with a kernel root) and the existing browser editor
subject to its independent source limit. For source-attested HKEX, use
the **bundled file**, not the unbundled entrypoint, as the proof input.
Source references in compiler diagnostics refer to the combined file; richer
per-file diagnostics, namespaces, explicit import declarations, dependency
resolution, module visibility and separate compilation remain open.

## Evidence

```sh
python3 -m unittest tests.test_htmlk_bundle -v
python3 scripts/test_htmlk_bundle_qemu.py
```

Local Linux output 25; repeated identical bundles and HKEX files match
byte-for-byte. Changing only the library square function yields real kernel
and Ring3 CPU output 27 instead of 25, with two kernel boots, two Ring3 ISO
boots and four user executions with frame reclamation. Negative checks cover
duplicate functions, recursion, missing library, extra roots, invalid tags,
incomplete comments, symlinks, existing outputs and source limits. Also
fixes the canonical parser's comment-position bookkeeping for CR and Unicode
line separators (HTMLParser tracks LF). Exact PR CI and public browser
verification are separate; hardware not tested.

## Future native backend

See [Issue #118](https://github.com/Eun-si123/html-kernel-os/issues/118).
Current native execution still uses generated C and GCC/TinyCC. Keep this
verified path until a shared typed IR and a C-free codegen backend are proven.
The bundle format does not depend on the choice of machine-code backend.
