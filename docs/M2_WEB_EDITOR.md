# M2-UX4 — real local HTML source authoring in the GitHub Pages Live Lab

**Scope:** locally author, download, compile with the existing native toolchain,
then import and boot a genuine BIOS ISO. This is **not an in-browser compiler**.
PR #108 passed exact-head native QEMU CI/Gitleaks and merged. The editor was
independently verified on the publicly deployed GitHub Pages site in Chromium.

## User workflow

1. Open the static [Live Lab](https://eun-si123.github.io/html-kernel-os/live/).
2. In **00 / WRITE SOURCE** edit the real HTML Kernel Language `<program><main>` app in the
   textarea. The page counts **UTF-8 bytes**, rather than JavaScript UTF-16
   characters, against the kernel ROMFS per-file limit of 4096 bytes.
   Empty or >4096-byte sources cannot be downloaded through this editor.
   There is no browser compile, syntax certification or executable preview.
3. Click **HTML 파일 저장**, downloading the exact current bytes to
   `htmlk-program.html`. The editor does **not** upload or send your code to
   a server. The browser's Blob/URL object is built from those same UTF-8
   bytes, and temporary object URLs are revoked after download initiation.
4. With the repository checked out on your own PC, use the real toolchain:

   ```sh
   python3 scripts/htmlk_check.py htmlk-program.html --target user --json
   python3 scripts/build_live_site.py --source htmlk-program.html --out-dir build/my-html-os
   ```

   The UI shows the second command and offers to copy it to your clipboard.
   Clipboard access depends on a secure context and permissions; it may
   fail, in which case the command stays visible for manual copying.
5. Choose `build/my-html-os/html-kernel-live.iso` in **내 빌드 ISO**, and
   `htmlk-program.html` in **같은 원본 HTML**. Boot the actual image in the
   existing browser x86-64 emulator. The page does not claim that editing
   the HTML without rebuilding the ISO changes CPU instructions.
6. Run `cat /source.html` on the real COM1 console and compare the CPU's
   actual ROMFS bytes against your selected source. Custom build manifests
   intentionally omit the default example's expected exit code `7`; then run
   `run /apps/hello.hke` to observe real Ring3 execution and frame reclaim.

## Positive and negative evidence

- Node tests: exact 4096-byte cutoff for ASCII, three-byte Hangul and
  four-byte Unicode emoji; empty source rejection, template byte fidelity,
  deterministic filename and existing real `build_live_site.py` command.
- Real native QEMU: the **exact exported editor JS template** is retrieved
  from `site/live/editor.mjs`, compiled by the existing HTML→C/HKEX/ROMFS ISO
  builder, booted in actual QEMU, and evaluated via guest COM1. It reports
  actual value `2026`, reclaims six user frames and the guest returns the
  unmodified original HTML bytes. Change `2026` to `2031` → different ISO
  bytes, different guest CPU output, same exact source round-trip and
  successful return to the UART shell. This is not JS text simulation.
- Local actual Chromium mobile (390px wide): textarea and build command
  visible without horizontal overflow. A real browser click on Download
  yields a `text/html;charset=utf-8` Blob containing the **exact modified
  current textarea bytes** and the fixed filename. No guest is booted or
  falsely marked `CPU RUNNING` after editing/download. UTF-8 boundary
  checked with Hangul: 4095 allowed, 4098 denied.
- Existing Live C local-ISO import, `cat` source comparison and real x86
  execution continue to be tested independently; the editor does **not**
  replace the immutable prebuilt public ISO or the guest emulator.
- GitHub CI/Pages gates use Node tests, static HTML assertions and native
  QEMU source mutation proof before publishing the editor's JS module.

## Limitations / security boundaries

- A static GitHub Pages site **cannot execute Python/GCC, compile a new ISO,
  or prove typed semantics** merely from a textarea. No source checker is
  reimplemented in JavaScript; the **existing compiler** remains the single
  source of truth. Use the local CLI for accurate errors and real builds.
- The web code alone does not prove an arbitrary ISO is trustworthy.
  SHA-256/source matching is a consistency test, not signing or isolation.
- Browsers may ask download and clipboard permissions. Use the visible
  command if clipboard copy is denied. Local source in the editor is not
  saved to a cloud account or persistent web storage and will be lost on
  page refresh unless downloaded. Reset asks before discarding edits.
- The actual guest is still a bounded experimental OS: no validated
  arbitrary code sandbox, calibrated x2APIC timer in the browser image,
  writable storage, SMP, or physical hardware proof (M6 remains NOT RUN).

**Future separate gate:** a genuinely browser-resident native compiler
would need the same grammar/codegen semantics, a browser-safe native
cross-toolchain or isolated builder, reproducible binary/ISO proof and real
CPU execution. Simply printing a JavaScript-computed answer cannot count.
