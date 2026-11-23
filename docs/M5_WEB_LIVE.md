# M5 Web Live — HTML-authored real Ring3 code on GitHub Pages

**Address when deployed:** `https://eun-si123.github.io/html-kernel-os/live/`. It is a **separate, dedicated page within the existing HTML Kernel OS GitHub Pages site**, not a new GitHub repository or separate domain. The previous Boot Lab stays available at `/html-kernel-os/play.html`.

## What actually executes

The source `examples/user-programs/html-u64-report.html` contains real `<repeat>`, `<print value="4294967296"/>`, `<print value="18446744073709551615"/>` and `<halt code="7"/>` instructions in the project's strict **HTML-shaped programming language**, **not** ordinary browser HTML.

GitHub Actions compiles that source through `compiler/htmlk.py` → C → genuine x86-64 native executable code → bounded HKEX program, adds the user image to the small read-only ROMFS, compiles the real kernel from `examples/kernel.html`, and creates a bootable Limine BIOS ISO. The browser uses the existing pinned, BSD-licensed x86-64 v86 WebAssembly emulator to boot **this real CD-ROM ISO**, SeaBIOS → Limine → 64-bit kernel. JavaScript never simulates the user's kernel output or produces pretend program exit markers. All guest console bytes are from the `serial0-output-byte` event; commands are sent as actual `serial0_send` bytes.

At the guest COM1 prompt, `help`, `ls`, `cat /welcome.txt`, `run /apps/hello.hke` and `exit` are genuine kernel commands. The `run` command enters Ring3 from real kernel code, prints full-width unsigned 64-bit results using native `INT 0x80` syscalls, returns status `M5_RUN_EXIT_CODE=7`, reclaims the task's six owned frames and resumes the prompt. `exit` runs the original HTML-derived kernel completion.

The separate site displays actual VGA, UART bytes, a read-only copy of the exact source, and checks SHA-256 of both the fetched HTML source and downloaded ISO against the same reproducible, source-generated manifest. **SHA-256 matching this public manifest is consistency evidence only, not code signing, provenance authentication, or a secure update mechanism.**

## Rebuild and independently verify

```sh
python3 scripts/build_live_site.py --out-dir build/live-site
python3 scripts/test_live_site.py --out-dir build/live-site
node --check site/live/live.js
python3 -m unittest tests.test_live_pages
```

The QEMU acceptance test intentionally uses the **exact ISO built for Pages** (with `--test-exit`, to allow deterministic VM completion via the QEMU debugexit device). Two complete genuine x86-64 BIOS boots each exercise real COM1 input, help, ROMFS listing/read, missing path rejection, two independently started user programs, their full-width numeric output, six-frame reclamation, status 7 and HTML kernel completion. The HTML app source and kernel source SHA-256 are recorded in the manifest and verified by the test.

The site is static. It **cannot** compile arbitrary user-edited HTML directly in the browser yet; that would require safely implementing the entire language compiler/linker/boot-image build pipeline in WebAssembly or a trusted separate build service, which this release does not claim. The existing x86-64 v86 WASM interpreter/emulator is not the native compiler.

## Deliberate compatibility/security boundary

The publicly served ISO is a **no-x2APIC-user-timer** variant. Its actual QEMU proof covers ROMFS, guarded synchronous CPU faults, Ring3 execution and serial interaction. x2APIC-based deadline control from M5-E2 is **not** claimed browser compatible or included here; an infinite or otherwise malformed program could freeze the guest until the user stops or reloads the browser emulator. The browser uses 128 MiB RAM, one CPU, a virtual read-only CD-ROM image and **no guest network device**, no host disk drives.

No physical PC, UEFI firmware, arbitrary native executable trust, SMP, FPU/XSAVE, FS/GS, writable filesystem, secure untrusted execution, or real hardware compatibility is implied. **Observed real browser execution (local test, 2026-11-23):** Chromium 158 in the isolated mini-PC Playwright container served the exact image/manifest/source on an in-container HTTP preview (no host firewall opening). Actual WASM x86-64 machine emitted the SeaBIOS VGA line `Booting from DVD/CD...`, then real COM1 `M3_IDT_READY`, `M5_CONSOLE_READY`, and `M5_PROMPT>`. Clicking actual UI shortcuts sent `help`, `ls`, `cat /welcome.txt`, `run /apps/hello.hke` **twice**, then `exit` through the emulator's `serial0_send()` API; independently observed native COM1 output contained both `4294967296` values and `18446744073709551615` twice, exactly **two** `M5_C_RING3_EXIT_OK`, **two** six-frame reclaim markers and **two** `M5_RUN_EXIT_CODE=7`, followed by `M5_CONSOLE_EXIT` and HTML-compiled native kernel completion. Page's exact source/ISO SHA-256 checks passed. At 390px mobile viewport the real VGA canvas measured 347×260 CSS pixels (4:3), no horizontal page overflow, dark media CSS verified. **This is observed local browser execution, not proof of published GitHub Pages deployment**. Test is manual Playwright observation, not automated CI; QEMU/image tests are separate. Release/PAGES checks remain pending until GitHub Actions actually deploy the proposed page.

## Public GitHub.io acceptance (2026-11-23)

**PR #96** exact head `4097795`: GitHub QEMU Actions `45152833650` and `45152894469` PASS, Gitleaks `45152895610` PASS; merged `b1aad1e`. Main Pages build/deploy run **`45153958869` SUCCESS**. At the real public URL `https://eun-si123.github.io/html-kernel-os/live/` Chromium was independently navigated to the published page, fetched its current ISO + HTML source, confirmed both SHA-256 values against the published build manifest, and booted actual x86-64 v86 WASM guest. Public real SeaBIOS VGA said `Booting from DVD/CD...`, COM1 said `M5_CONSOLE_READY`/`M5_PROMPT>`, then two separately clicked `run /apps/hello.hke` commands produced **two** `M5_C_USER_VALUE=18446744073709551615`, **two** `M5_C_RING3_EXIT_OK`, **two** `M5_C_USER_FRAMES_RECLAIMED`, **two** `M5_RUN_EXIT_CODE=7`; genuine `exit` produced `M5_CONSOLE_EXIT` followed by the original HTML-derived native kernel completion. The public build ISO differs in SHA from the local preview due to source/build environment differences, so the **actual public published manifest** was checked, not an assumed local hash. This is observed **public Pages real browser execution** (unlike earlier local preview proof). Full M5 security / physical PC boot still OPEN.
