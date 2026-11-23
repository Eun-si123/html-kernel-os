# M5-D1 — actual UART `run` command launches ROMFS user code in Ring 3

**Status:** M5-D1 PR [#72](https://github.com/Eun-si123/html-kernel-os/pull/72) **merged into main** as `4bcc4ca`; exact-head GitHub Actions native test runs `45127468347` and `45127462226` and Gitleaks `45127465708` SUCCESS, plus local real BIOS QEMU PASS. Prerequisite M5-C1 PR #70 is merged as `4d3d735`. Post-merge main CI is verified separately. This is a **single trusted build-time embedded user executable** experiment; not a generic untrusted-program OS or broad hardware claim.

## Execution contract

- Build with `--exception-idt --tss-ist --romfs-run-console`. This is independent of existing `--romfs-console` (M5-B) and `--user-loader-probe` (M5-C1) modes; incompatible probes are rejected. Default kernel and public Boot Lab are unchanged.
- Reuse M5-A bounded ROMFS image and M5-C1 `HKEX` separate x86-64 machine-code builder. The kernel still receives actual characters from the QEMU 16550 COM1 hardware, not a simulated browser console. New `run /canonical/path` command is accepted only in the combined mode. The existing `help`, `ls`, `cat`, and `exit` work unchanged.
- Before `run` enters Ring3, the trusted kernel copies at most 4KiB of ROMFS data into bounded kernel scratch and checks the HKEX header, size, entry and checksum. Bad path returns `M5_ERR_INVALID_PATH`; absent file returns `M5_ERR_NOT_FOUND`; existing but malformed file returns `M5_ERR_BAD_EXEC`. All are handled **without leaving the console**.
- After successful preflight the kernel rereads and revalidates the **actual immutable ROMFS bytes** inside M5-C1's user loader, creates a fresh user CR3 and user RO code/RW stack from existing M4-C1 helpers, and enters real CPU CPL3 using `iretq`. The separate program performs restricted `INT 0x80` syscalls, reports its own source-derived number, explicitly exits and reclaims all six owned physical frames. Debug output is mirrored to actual COM1 TX as well as port E9.
- The shell prints `M5_RUN_DONE` and another `M5_PROMPT>`. Running the same app twice creates and destroys two separate user execution contexts. `exit` then invokes original HTML-generated kernel logic, with a successful QEMU test exit 33.

## Proof

```sh
python3 -m unittest tests.test_m5_run_command tests.test_console_runner -v
python3 scripts/test_m5_interactive_run.py
python3 scripts/run_m5_console.py --with-user-program
```

`tests/test_m5_run_command.py` uses native GCC UBSan -O0/-O3 to reject noncanonical paths, malformed command spelling and traversal while retaining the older parser behavior. `scripts/test_m5_interactive_run.py` builds and actually boots x86-64 BIOS QEMU, sending live UART bytes into COM1: `help -> ls -> cat -> run missing -> run invalid text -> run traversal -> run invalid root -> overlong input -> run valid twice -> unknown -> exit`. The test separately checks COM1 UART TX user-program data, the independent byte-level source mutations (`2026 -> 2027` user assembly and edited HTML), idle/no-input guard, malformed `HKEX` integrity rejection with **continued shell operation**, and dangerous command-line combination rejection.

## Security and scope boundaries

- Only **trusted build-time** embedded apps are supported; FNV is a corruption check, **not** code authentication or a sandbox certification. If an otherwise well-formed app triggers a CPU fault or uses an unsupported syscall, current M5-C1 handler **fails stop** rather than recovering the console. The tests only claim recovery for **invalid paths / missing or damaged *files before execution***.
- No executable loader from host disks, no writable filesystem, no generic ELF/PE relocation, no arbitrary HTML-to-user-mode compilation, no copyin/copyout syscall API, no timeout preemption of user-loaded app, no FPU/FS-GS/SMP/UEFI/physical PC proof or production multi-process isolation.
- This closes the **bounded interactive proof** of one command-read-run-exit sequence, not the general M5-C2/M5-D runtime, trusted user ABI, broader reliability or the physical M6 milestone.
