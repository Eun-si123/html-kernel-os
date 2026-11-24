# M5 Web-D — actual BIOS/VGA and CPU COM1 boot journal

**Scope:** a bounded, user-readable record of what the **real browser x86-64 emulator** displayed and emitted, including the first BIOS text. It can replay that evidence after the native guest already finished booting. PR #110 passed exact-head CI/Gitleaks, merged and was independently validated
on the public GitHub Pages site in actual Chromium. Physical hardware is untested.

## What it does

- Attaches actual `screen-put-char` VGA and `serial0-output-byte` COM1 event handlers **before starting the v86 CPU**. The v86 instance uses `autostart:false`, then runs only after `emulator-ready` has been received and handlers are installed. The recorded stream distinguishes host lifecycle events (`VM HOST`), observed firmware text (`BIOS VGA`) and genuine CPU serial lines (`CPU COM1`).
- Reconstructs selected boot text such as `SeaBIOS`, `Booting from DVD/CD...`, `Limine` and `iPXE` from actual VGA cell writes, and completes real COM1 text only when a newline arrives. No hardcoded example COM1 output is inserted. Firmware lines repainted in bursts are de-duplicated by replacing a genuine partial observation with its observed full text.
- Gives visitors a **boot journal** on `/live/`: replay from the start, pause, step by one event, scrub the position, and select 0.5× / 1× / 2× / 4× **record playback speed**. These are browser-reception elapsed timestamps, not virtual CPU cycles.
- Lets the real VGA canvas fill the entire panel width while keeping 4:3 proportions and fullscreen behavior. The former hardcoded 545px maximum left unused horizontal space.
- Caps the journal at **240 entries**, each at most 240 text characters, without allowing guest strings to become HTML markup: rendering uses `textContent`, never `innerHTML`.

## Reproducible evidence

```sh
node --check site/live/live.js
node --check site/live/journal.mjs
node --test scripts/test_live_boot_journal.mjs
python3 -m unittest tests.test_live_pages
```

The Node tests verify only completed real UART lines are recorded, out-of-bounds VGA cells and bad UART values are discarded, partial SeaBIOS strings are updated using observed characters, bounded logs do not grow indefinitely, and raw guest text is never evaluated.

**Independent actual Chromium local test:** booted the repository's real BIOS ISO through the pinned browser v86 after enabling pre-CPU listeners. The journal recorded real events in order:

```text
[VM HOST] emulator-ready
[VM HOST] emulator-started
[BIOS VGA] SeaBIOS (version rel-1.16.2-0-gea1b7a0)
[BIOS VGA] Booting from DVD/CD...
[CPU COM1] M3_IDT_READY
[CPU COM1] M5_CONSOLE_READY
```

The browser reached the real guest `M5_PROMPT>`, and replay controls could go from position 0 to the captured final event **without restarting or slowing the CPU**. The VGA canvas measured **712 CSS px**, exactly the enclosing **712px panel**, correcting the earlier 545px cap. Real CPU stdout/ROMFS/HTML source-change acceptance remains independently covered by the existing Live C and M2-UX4 tests.

## Honesty and limitations

- This is **real observed event capture**, not a complete BIOS tracing interface. Only text visible through supported VGA/COM1 hooks can be captured; early hardware actions with no VGA/UART events or text repainted too quickly may be absent.
- **Playback is not CPU throttling.** It changes only the journal display speed, never x86 instruction frequency. A CPU hang must still be stopped/reloaded; browser x2APIC timeouts are not certified.
- SeaBIOS, Limine and the ISO loader are **native firmware/boot artifacts**, not compiled HTML. HTML Kernel Language compiles to the actual user/kernel binaries in the image. An ISO is not made solely of HTML documents.
- The journal does not introduce native capabilities, guest networking, host disk access or an arbitrary-program sandbox. M6 physical PC trials remain **NOT RUN**. Logs can contain arbitrary guest-provided strings; avoid presenting captures as verified third-party image provenance.

This feature addresses the longstanding request to see the **very beginning** of an otherwise fast native browser boot while preserving the separation between the genuine virtual CPU and replay UI.
