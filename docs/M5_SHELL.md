# M5-D — actual interactive native terminal → ROMFS → user program

**Status: independent M5-D bounded acceptance proof PASS on mini-PC BIOS QEMU. Exact-feature-head GitHub CI and merge remain to be verified. This is not a complete general-purpose OS.**

## What actually runs

- `--romfs-shell` opt-in builds a genuine x86-64 Limine kernel with the real UART M5-B command parser, M5-A immutable kernel ROMFS, and M5-C1 HKEX user loader in **one guest image**. This mode internally enables IDT, TSS and dedicated #PF IST; all incompatible M4 probes and the default build remain separate.
- Actual emulated 16550 COM1 hardware receives real input. Guest commands: `help`, `ls`, `cat /path`, `run /apps/hello.hke`, `exit`; the new `run` grammar checks canonical paths and accepts **only** the explicitly allowed application image path. `run /missing.hke` and unrecognized options are rejected; ROMFS binary is not printed as console text.
- On `run`, guest reads the exact embedded HKEX bytes through M5-A, validates header/length/checksum, installs M4-C1 supervisor/private user memory, uses CPU `iretq` to enter **CPL3**, accepts three bounded `int 0x80` register-only operations, and returns to the **same working kernel UART shell** after reclaiming all six task pages. The program can be run **twice** in one QEMU boot; each run reinitializes a bounded ownership registry and checks all releases.
- The kernel console mirrors user-mode syscall results to both native debugcon and COM1, making them visible to a real interactive terminal rather than merely a test log. `exit` only terminates the shell and then executes the independently HTML-generated native kernel.
- The original browser Boot Lab ISO, normal kernel ISO, M4-D concurrent CPL3 preemption/fault proof and individual M5-A/B/C1 opt-in images are **not changed by default**.

## Reproduce

In a real interactive Ubuntu terminal with GCC, xorriso and x86-64 QEMU:

```sh
python3 scripts/run_m5_console.py --shell
```

Then type `help`, `ls`, `cat /welcome.txt`, `run /apps/hello.hke`, `run /missing.hke`, `run /apps/hello.hke`, `exit`. The runner uses no network or host storage mapping inside QEMU. An independently built test ISO can be made with:

```sh
python3 scripts/build_boot.py --romfs-shell --test-exit --out build/m5-shell.iso
python3 scripts/test_m5_shell.py
python3 -m unittest tests.test_shell_command tests.test_console_runner -v
```

The actual BIOS QEMU test covers: live COM1 input, full help/list/file read, HKEX binary text refusal, **two distinct CPL3 launches** with successful kernel return and all frames reclaimed, nonexistent/traversal/unknown/overlong command rejection, no-input idle with no hidden execution, changed HTML source to different native ISO/output, separately changed x86-64 user assembly from 2026 to 2027 to different native ISO/output, a genuinely corrupted HKEX image rejected in-guest **after user input and before CPL3** with QEMU exit 53, and unsafe CLI combinations rejected before ISO creation. Host GCC UBSan `-O0/-O3` validates parser path and bounded-line behavior.

## Boundaries (no unsupported OS claims)

This is still a **single trusted application format/path** with no ELF/PE loader, standard userland, pointer-capable generic syscalls, general executable enumeration, disk persistence, network, USB input, framebuffer window terminal, production security model, general task scheduler, user CPU time quotas, timer preemption during `run`, arbitrary application memory ownership, FPU/FS/GS or SMP context, UEFI or real PC test. The shell halts the kernel on an invalid executable or illegal CPU user instruction; it does not recover to the prompt after such a fault. The FNV hash is not a signature. A malicious executable can spin forever with interrupts disabled; **do not accept untrusted programs**. The earlier M4-D timed preemption/fault-survivor prototype is separate and not a general process runtime.

**Bounded M5-D QEMU gate** has been executed. To claim full M5 or a real usable OS would require a real multi-program lifecycle, syscall pointer checking and fault isolation integrated with the shell, budget/preemption, stable program format, broad device input, and physical-hardware evidence. See [M0–M6 roadmap](ROADMAP.md).
