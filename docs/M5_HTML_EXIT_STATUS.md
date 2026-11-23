# M5-F4 — HTML user-program exit status on the real native UART shell

**Scope:** an opt-in, build-time trusted HTML-to-HKEX CPL3 user executable on single-vCPU QEMU BIOS. Local host+real-QEMU acceptance PASS; new PR exact-head GitHub CI/security scan and merge are separate gates. This is **not** a general-purpose POSIX process ABI or untrusted-code sandbox.

## Use it

User program (for example, `examples/user-programs/html-message.html`) may end with:

```html
<print>Hello from user code!</print>
<halt code="7"/>
```

To build and run a real user-program ISO on Ubuntu with GCC, QEMU and xorriso:

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-message.html
# Use a copy with <halt code="7"/> to see a nonzero exit status
# COM1 prompt: run /apps/hello.hke
# ... M5_C_USER_FRAMES_RECLAIMED
# ... M5_RUN_EXIT_CODE=7
# COM1 prompt: exit
python3 scripts/test_m5_html_exit_status.py
python3 -m unittest tests.test_html_user_exit_status -v
```

`<halt/>` and `<halt code="0"/>` preserve `M5_RUN_DONE`. Values **1..255** produce `M5_RUN_EXIT_CODE=N` on both QEMU debugcon and actual COM1. The exit result is available only once the privileged supervisor has restored the original CR3/stack and reclaimed all six physical frames; neither source-side HTML nor guest user code directly writes a UART port. Every subsequent launch starts with an independently zeroed status. This is an *application return status*, not an emulator/guest boot exit code and does not by itself reboot the machine.

## Implementation and trust limits

- `compiler/language.py` accepts an optional **ASCII decimal literal** `code` only on `<halt>` in `0..255`, rejecting negative, hexadecimal, expressions, whitespace, invalid Unicode numerals, oversized numbers, duplicated or unknown attributes. The top-level final `<print>` + final `<halt>` requirement still applies to a user program.
- `compiler/htmlk.py` rejects `code` on **kernel and Linux targets**, which retain their old `<halt/>` semantics and native behavior; the `user` target emits a direct `INT 0x80` ID 1 with the validated literal in RDI.
- `scripts/build_boot.py` enables `HTMLK_M5_USER_EXIT_STATUS` **only with `--user-app-html`**. Legacy standalone M4/M5-C1 and other M5 assembly-only modes continue rejecting any nonzero exit argument. Under that opt-in build, the Ring3 syscall dispatcher requires the existing live user process, handshake/report, register privilege/CR3 checks, and an 8-bit exit argument; it stores status only on valid syscall-1 termination and never IRETs to an unchecked post-syscall RIP. Compatible with the merged PR #89 EOF `INT 0x80` safety boundary.
- `boot/serial_console.c` prints the bounded decimal result only after the protected user execution returns and the existing fault, invalid syscall and timeout classifications have been checked. An invalid exit argument is reported as `M5_ERR_USER_SYSCALL`, and its task is retired with the ordinary six-frame reclaim rather than corrupting the following app's status.

## Independent, genuine CPU test evidence

`scripts/test_m5_html_exit_status.py` creates distinct, actual bootable ISOs for HTML exit 0, 7 and 255 and compares their bytes. Three complete BIOS QEMU x2APIC boots for code 7 each execute a healthy HTML app, a separately hand-assembled invalid exit 256 app, a separate executable ending **exactly with a valid `INT 0x80` exit 7**, a real Ring3 #UD faulting app, a genuine nonyielding CPL3 task forcibly interrupted by the x2APIC timer, then the healthy HTML app **again**, a live help command and final HTML-derived native kernel exit. The test checks status, COM1+E9 output, invalid-syscall classification, distinct frame reclamation markers, lack of fatal error markers, and guest exit. Separate ISOs prove code 0 retains `M5_RUN_DONE`, 255 prints the bounded maximum, and changing only the user HTML source changes the ISO/native UART output. An HTML code 256 build fails before an ISO is emitted. An old **M5-C1** standalone code-7-at-EOF image remains fail-stop (QEMU status 53), proving no global syscall ABI broadening.

`tests/test_html_user_exit_status.py` checks the compiler's literal bound, malformed inputs, target isolation and reproducible generated C; all existing M2/M4/M5 tests remain part of the CI regression. Full image tests use a virtual CD and `-net none`, never physical disks.

## Still open

This is a tiny, synchronous one-task-at-a-time status code. No exit-code variables or expressions yet, no arguments/env, process launching from user space, pipeline/IPC, writable disk, ELF/shared libraries, SMP/FPU/FS/GS context, wall-clock timer calibration, UEFI or physical PC boot. FNV-1a is only an accidental-corruption check and **does not authenticate external code**. M5-E3 general isolation hardening and M6 physical-device trial remain distinct. See [roadmap](ROADMAP.md) and [status](STATUS.md).
