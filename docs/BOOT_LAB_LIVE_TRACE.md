# Boot Lab — live BIOS/COM1 observation and ISO-matched HTML source

## What is real

- **BIOS VGA text:** the pinned v86 build emits `screen-put-char` events containing actual CPU-emulated VGA text cell writes `[row, col, char]`. The web page buffers cells and displays only completed, observed SeaBIOS/boot-medium messages. This is real BIOS VGA text, **not serial COM1 or a fabricated Limine progress report**.
- **VM status:** `emulator-ready` and `emulator-started` are v86 lifecycle events. They indicate initialization/CPU running, not that the kernel reached a particular C function. The timeline shows actual elapsed wall time from the user's Boot click.
- **Live COM1:** `serial0-output-byte` updates the raw, visible console **for every received byte**, including the first. It does **not** buffer the entire expected output and hide it until verification as the old Boot Lab did. Expected-output equality is checked separately when the final exact string is observed; mismatches retain raw output and disable the 'verified replay' button.
- **Actual HTML source:** Pages ships only the eight `examples/*.html` files used in the same workflow to compile the eight visitor ISOs. The page fetches the selected source read-only and renders it with `textContent`. A matching literal `<print>text</print>` line is highlighted only after the real COM1 completes that same text line. Numeric expression results, branches and function evaluations are **not instrumented** as exact source instructions. Before the first COM1 byte, the page explicitly says that BIOS and Limine execute native code, **not this HTML**.
- **Actual virtual CPU observation mode:** selecting '느린 관찰 (실제 VM)' before boot uses supported v86 `stop()` and `run()` calls, alternating approximately 65 ms CPU execution with 450 ms of paused CPU time. This changes actual guest CPU progress in *wall-clock time* but **does not lower the CPU clock frequency or create a hardware debugger**. Browsers schedule timers imprecisely, so these numbers are nominal. Normal-speed mode is available and recommended for slow devices.
- **Manual CPU pause/resume:** real v86 stop/run calls. '**기록 다시 보기**' is separate: it only plays back already-verified COM1 text, without rebooting or changing CPU state.

## ISO files are not HTML documents

The native `scripts/build_boot.py` process compiles `examples/kernel.html` into generated C, then produces freestanding x86-64 machine code and an ELF kernel. `xorriso` packages `/boot/kernel`, `/boot/limine/limine.conf`, the pinned Limine BIOS/UEFI boot components and `/EFI/BOOT/BOOTX64.EFI` into a hybrid boot image. The **original `.html` file is not included in the ISO**. The website's extra `public/examples/*.html` files are an educational, source-matched read-only view outside the ISO.

## Validate separately

```sh
node --check site/play.js
python3 -m unittest tests.test_site -v
python3 -m unittest discover -s tests -v
```

The Pages workflow builds the eight ISOs, copies the same exact eight source files into `public/examples/`, and runs the published-artifact credential scanner before deployment. The CI static tests enforce the source/ISO mapping, actual v86 API paths and controls. These static tests alone **do not prove a browser boot**.

Real browser validation must separately confirm that BIOS `screen-put-char` produces observed SeaBIOS/VGA entries **before COM1**, COM1 bytes become visible immediately rather than after exact match, the source loads and highlights a proven literal print line, actual CPU time slicing proceeds to successful exact output, manual pause/resume works, replay works without replacing live bytes, and mobile layout has no overflow. Chrome/v86 is not proof of UEFI or physical hardware support.
