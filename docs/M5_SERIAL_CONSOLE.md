# M5-B — real x86-64 BIOS guest UART console and read-only file commands

**Gate:** preparatory local M5-B **PASS under native BIOS QEMU**. Tests and source are included on an independent feature branch; a passing exact GitHub PR CI run is necessary before claiming integration. This remains separate from M4-D and does **not** complete M5: independent CPL3 user program loading is not implemented.

## Native execution path

- `scripts/build_boot.py --romfs-console --test-exit` compiles `boot/serial_console.c` and `boot/serial_command.c` into the native ELF kernel, alongside the previously verified M5-A immutable ROMFS bytes. No JavaScript terminal simulator, prerecorded script interpreter or Linux host file I/O runs in the guest.
- The guest initializes the **QEMU emulated 16550 COM1 hardware** (I/O ports `0x3f8`, LSR `0x3fd`), polls the UART Data Ready bit for live input, and echoes keystrokes via actual UART TX; debugcon `0xe9` independently captures output. Input is fed **after** QEMU emits `M5_CONSOLE_READY`. The hardware's finite FIFO requires paced injection in the host integration test to avoid legitimate UART overrun.
- A 96-byte bounded ASCII command-line parser accepts CR/LF, backspace and delete, rejects other control/non-ASCII bytes, long lines and previously invalid lines until newline. No dynamic allocations. Whitelisted commands: `help`, `ls`, `cat /canonical/path`, `exit`. `cat` reads the **actual M5-A ROMFS** in 17-byte chunks. It rejects non-text bytes as unsupported rather than silently outputting control sequences; absent and traversal paths return distinct errors. `ls` uses validated sorted ROMFS entries.
- `exit` returns to the **original HTML-generated kernel code**, which terminates in test images with QEMU's `isa-debug-exit` successful code 33. Without user input, the guest does not proceed into generated HTML. Incompatibility with other memory, IRQ, user-mode and M5-A probe modes is rejected at build time.
- Default ISO, existing M4 probes, website/Pages and physical storage remain unchanged. No device driver beyond the single trusted I/O port, no SMP/UEFI/USB keyboard, no user pointer or memory copy-in/out, no privilege boundary for shell commands, no dynamically loaded user program, no networking or writable disk.

## Reproduce / evidence classes

```sh
python3 -m unittest tests.test_serial_command -v
python3 scripts/test_m5_console.py
python3 scripts/build_boot.py --romfs-console --out build/html-kernel-m5-console.iso
```

`tests/native/test_serial_command.c` is compiled with host GCC `-O0/-O3` and UBSan: command classifications, canonical paths, oversized/invalid line recovery, backspaces and control bytes. This is **not** proof of UART hardware.

`scripts/test_m5_console.py` builds genuine Limine x86-64 ISOs and spawns headless BIOS QEMU with `-serial stdio` for actual UART input and `-debugcon` capture. It asserts exact user-input-driven command responses, missing/traversal/unknown/overlong/control rejection, recovery, and correct HTML code execution; asserts a no-input idle oracle has neither guest progress nor generated HTML. It then mutates the ROMFS bytes and the HTML source **independently**, builds new ISOs and proves they really change the native guest output. Bad option combinations are rejected before ISO creation.

## Milestone follow-on

- M4-D: complete real user-mode **timer preemption with per-task CR3, TSS.RSP0 and fault isolation**, including fail-stop negatives. No M4 completion assertion without that gate.
- M5-C: introduce separate loaded CPL3 program with explicit trusted initial executable format, restricted syscalls, ownership and negative tests; source-derived HTML user binary desired once compiler target is safe.
- M5-D: one interactive test must enter commands, read embedded files, **execute a separate user program**, reject invalid inputs and keep the rest of the kernel alive. Only then call M5 accepted.
- M6: controlled supported physical-hardware evidence and recovery; never infer compatibility from QEMU.
