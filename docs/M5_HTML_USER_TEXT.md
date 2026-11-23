# M5-F2 — checked read-only user text (real Ring 3, ROMFS, COM1)

**Status:** native QEMU BIOS and GCC UBSan O0/O3 locally verified on an opt-in development branch. Exact PR-head CI and merge separately pending. The system is not an untrusted-executable sandbox or broadly compatible OS.

## One-command live console

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-message.html
# Inside the native QEMU COM1 shell: run /apps/hello.hke; help; exit
python3 scripts/test_m5_html_user_text.py
python3 -m unittest tests.test_user_text_policy tests.test_html_user_text -v
```

`examples/user-programs/html-message.html` uses the **same** M2 typed HTML parser as the kernel and Linux compiler. `<print>Hello from HTML user mode!</print>` becomes a `static const` ASCII array in the single mapped read-only user code page; it is **not interpreted as markup at boot**. The new M5-F2 `INT 0x80` syscall ID **3** accepts `RDI` = user pointer and `RSI` = byte length; the kernel checks the current saved CPL3 interrupt frame, its own active private CR3, a single unmodified user code page, 1..96 bytes inside actual loaded code length (subtract-first arithmetic avoids overflow), printable ASCII in every byte except mandatory terminal newline, and that no report has yet succeeded. It **validates all bytes before output**, then sends to actual COM1 TX and debugcon. Out-of-bounds, zero, huge, kernel-space or stack pointers, and ESC/control bytes cause a **per-user-program** `M5_ERR_USER_SYSCALL` and full 6-frame reclaim; no partial terminal control sequence is emitted. The previous register-only numeric report syscall ID 2 remains independently available.

## Crucial position-independence fix

The generated string was initially linked from `R_X86_64_32` absolute relocation and baked into the HKEX payload as address `0x60`, **not** the real CPL3 virtual code address. A genuine QEMU attempt correctly rejected it as an invalid user pointer without crashing the shell. Rather than weakening the kernel memory-range policy, `scripts/build_html_user_image.py` now compiles with `-fpie`, supports PC-relative `.rodata` in `scripts/user_program.ld`, and **rejects non-PC-relative object relocations before final link**, since the final ELF itself can misleadingly report *no relocations* after an unsafe absolute address has already been resolved. The resulting real x86-64 app passes the guarded user-pointer contract in actual QEMU.

## Native and negative evidence

`python3 scripts/test_m5_html_user_text.py` executes three genuine BIOS QEMU boots using guest COM1 UART input: a normal HTML-derived user app **twice**, three distinct real CPL3 assembly programs passing forbidden supervisor pointer, `UINT64_MAX` length, and an in-range ESC control payload, then a healthy UART `help` and an independent non-yielding Ring3 program retired by genuine x2APIC. Every rejected user task reclaims exactly six owned pages; normal tasks also reclaim theirs, console remains interactive, and final HTML kernel output returns with normal QEMU debug-exit 33. A **mutated user string** and **mutated kernel HTML** each produce distinct ISOs and actual guest UART/kernel output, respectively.

`tests/native/test_user_text_policy.c` runs with GCC `-fsanitize=undefined -O0/-O3`. `tests/test_html_user_text.py` tests the shared compiler's ASCII bound/terminal control denial, no user OUTB, generated literal inclusion/checksum, absolute relocation rejection and PIC. The existing M5-F1 numeric program and older M4/M5 modes must remain regression-clean.

## Hard limits

A single final **printable ASCII** literal (at most 95 visible bytes plus one newline) or a single numeric report per program, not arbitrary pointer/string length, no Unicode/format strings/terminal control characters. Only the trusted build-time RO code page can be read; user stack, dynamic strings, kernel memory and separate user data pages are deliberately unsupported. No dynamic file writes, multiple text outputs, general user copyin/copyout, SMP, FS/GS/FPU save, arbitrary binaries, actual device testing or calibrated timeouts. The checksum in the HKEX file is **not** an authenticity signature; caller supplies trusted source at build time.
