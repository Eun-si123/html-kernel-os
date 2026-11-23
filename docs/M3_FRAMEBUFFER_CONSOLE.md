# M3 native framebuffer console (opt-in experiment)

## Why this exists

The old Boot Lab showed serial text beside a black virtual PC monitor. A real OS kernel should also be able to draw pixels in its own bootloader-supplied display. This feature adds a **native x86-64 Limine framebuffer text path**, not a JavaScript overlay or an HTML/CSS screen simulation.

It remains deliberately opt-in even though **real QEMU BIOS framebuffer-pixel readback and the independently captured QEMU VGA monitor screenshot both passed** (branch CI `45095698115`, source `1a82b79`). The actual v86 browser monitor is not verified yet. The ordinary ISO, COM1 output, existing site/Pages workflow, and Linux target are not changed.

## Runtime path

```text
examples/framebuffer-kernel.html
   -> compiler/htmlk.py -> freestanding C -> x86-64 kernel ELF
   -> Limine loads kernel + provides optional RGB framebuffer response
   -> boot/kernel_entry.c validates metadata and attaches mapped framebuffer
   -> boot/console_fb.c renders 5x7 original ASCII glyphs (2x pixels)
   -> source-generated <print> writes: debugcon + COM1 + RGB pixels
```

- Build: `python3 scripts/build_boot.py --source examples/framebuffer-kernel.html --video-console --out build/html-kernel-video.iso`
- The framebuffer response is a trusted Limine bootloader handoff, not a user-supplied raw pointer. Only 32-bit packed RGB with non-overlapping 8-bit channels, aligned pixels, bounded dimensions/pitch and bounded total memory is accepted. Other modes disable video safely; serial/debugcon keeps working.
- The display has an original minimalist dark palette, fixed heading, basic line wrapping and a cleared body region on overflow. Glyphs cover uppercase English letters, digits and common ASCII punctuation. Lowercase is displayed uppercase; non-ASCII bytes render a visible replacement glyph. **Korean/Unicode text, scrolling/history, keyboard and interactive terminal editing are not implemented.**
- The framebuffer is written directly through a mapped virtual address. This is **not** a general graphics driver, page-table manager, desktop, GPU acceleration or physical-hardware compatibility guarantee.
- In test-only mode, `--video-console --video-test --test-exit`, the kernel reads back a pixel from the last source-generated glyph. If no framebuffer or pixel readback fails, it reports `FB_PIXELS_FAIL` and triggers non-success QEMU exit 41; successful evidence is `FB_PIXELS_OK` plus normal QEMU test exit 33. A headless QEMU framebuffer readback is stronger than serial-only evidence but does **not** replace a screenshot/eyeball check of the actual browser monitor.
- `tests/test_video_console.py` compiles and exercises the same freestanding framebuffer rasterizer using real RAM under GCC UBSan -O0/-O3 with border sentinels and malformed-mode cases. `scripts/test_video_console.py` builds and boots the real HTML-derived source and a changed-source variant in QEMU; mere compilation does not count as proof.

## Independent screenshot and x86-64 CPU ISA evidence

`python3 scripts/test_video_screen.py` starts a normal non-debug-exit QEMU guest, waits for exact HTML-derived debugcon output, issues the QEMU monitor `screendump` command, and checks the **actual emulator VGA display buffer** for the expected green header, dark body and first source-generated glyph pixels. It exports a lossless PNG (`build/html-kernel-video-visible-screen.png`) for the CI artifact. This is stronger than merely checking in-kernel memory writes, but does not verify v86/browser visual output. RGB mode fallback is exercised by the independent native C test.

First attempts found a real guest crash: QEMU returned 0 with no serial bytes. CPU exception tracing showed `#UD` at RIP `ffffffff8000185d`; direct disassembly revealed `SHLX` (BMI2 extension) emitted by hosted GCC and unsupported by the default QEMU CPU. Pinning the freestanding target to `-march=x86-64 -mno-bmi2` fixed it, without relaxing RGB safety checks or hiding the failure.

## Why not invent an OS screen in JavaScript?

Rendering the serial log in a CSS canvas beside v86 would improve appearances but still leave the actual guest screen empty. This code makes the kernel emit its own pixel writes; the browser is only an emulator and is not responsible for synthesizing the text.

## Scope, tradeoffs and follow-up

1. Require a reproducible **real BIOS QEMU** framebuffer readback and a source mutation negative control.
2. Verify the actual **visible v86 monitor pixels** under Chromium/Playwright before wiring an ISO to the public Boot Lab. No GitHub Pages deployment in this PR.
3. Test framebuffer modes (including 24-bit/unavailable) and avoid touching unsupported layouts; implement a bounded scrolling text buffer, UTF-8 font pipeline and keyboard/input as separate milestones.
4. Keep M3 page tables and exception handlers as distinct work. Requesting a framebuffer does not complete M3.

Relevant design critique: [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md). Actual evidence: [STATUS.md](STATUS.md).
