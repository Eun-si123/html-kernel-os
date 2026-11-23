# M5-E2 — real CPU x2APIC timeout of nonyielding user program

**Status:** opt-in, QEMU BIOS single-vCPU native proof; local acceptance PASS. PR #79 merged as `220e657` after exact-head GitHub QEMU validation and Gitleaks PASS; no physical device test. **Not a production process security boundary.**

## Build and manually run

```sh
python3 scripts/test_m5_user_timeout.py
python3 -m unittest tests.test_user_timeout_frame tests.test_console_runner -v
python3 scripts/build_boot.py --exception-idt --tss-ist --romfs-run-console --user-fault-recover --user-timeout --test-exit --out build/m5-e2.iso
python3 scripts/run_m5_console.py --with-user-program --recover-user-faults --user-timeout
```

In the interactive Linux terminal, run `run /apps/spin.hke`, then `run /apps/hello.hke`, then `exit`. The first app is **independent x86-64 executable code in immutable ROMFS**; it loops forever at CPL3 with no explicit syscall, yield, or sleep, so *only a real external CPU IRQ* can stop it. The second app proves the original COM1 shell and the private-CPL3-page allocator remain usable after reclaim. QEMU uses `-M q35 -cpu qemu64,+x2apic -smp 1 -m 256M`, a virtual read-only CD image, no host disk/network. The existing browser/normal boot mode is untouched.

## What the actual CPU does

- Before IRETQ to Ring3, the kernel validates a separate HKEX program through the existing M5-C1 ROMFS loader and creates its owned PML4/PDPT/PD/PT, read-only executable user page and writable stack. As in M4-D, QEMU's actual local x2APIC timer is enabled (IRQ vector `0x40`), with a spurious handler at `0xff`. IRET uses IF=1 **only in this opt-in mode**; the normal native kernel shell has IF=0.
- The IRQ enters on the trusted TSS.RSP0 kernel stack and uses **the existing M4-D Ring3 ISR assembly**, which saves/restores all 15 GPRs and the actual 5-word CPU user interrupt frame. A separate, host-testable M5 frame guard validates the exact 160-byte IRQ frame address, RIP/code bounds, CS/SS, user RSP, IF/IOPL/NT/VM, active owner and current CR3. No user pointer is trusted or dereferenced by this path.
- Each genuine timer IRQ returns with x2APIC EOI and IRETQ until the **fourth** verified IRQ. The fourth ends the user program on its trusted interrupt stack, restores the original kernel CR3 and saved shell call stack with the existing M4-C1 handoff, disables and masks the timer, checks all six owned physical pages are released, and reports `M5_ERR_USER_TIMEOUT` followed by another real COM1 `M5_PROMPT>`.
- The x2APIC initial count (`1000000`, divide register `3`) is an **uncalibrated emulator-specific interrupt budget**, not a wall-clock millisecond SLA. This is an actual four-interrupt limit for one user program, **not** preemptive scheduling of several dynamic processes.

## Native test acceptance and negatives

`scripts/test_m5_user_timeout.py` executes **three entire QEMU BIOS boots**, and in each sends `run spin → timeout → run valid → run CPU fault → run valid → run spin → timeout → run valid → exit`, asserting real debugcon and UART output order, three successful valid app executions, two timeout frame reclaims and one CPU-fault reclaim, then exact HTML-generated native kernel output. The same test proves a no-input shell remains idle, a modified HTML source yields a distinct native ISO and output, and a separately modified user assembly yields a distinct ISO and real CPL3 `INT 0x80` result.

Crucial negative controls: on `-cpu qemu64,-x2apic` the guest **rejects** this mode with failure exit 57; with the **real APIC timer intentionally masked** through `--user-timeout-mask`, the nonyielding Ring3 app makes no IRQ progress and never returns to a prompt (host-enforced finite timeout). Other unsafe builder flag combinations fail without creating an ISO. `tests/test_user_timeout_frame.py` runs the standalone frame policy under GCC UBSan at `-O0` and `-O3`, rejecting forged CPL0/SS, wrong CR3, disabled IF, IOPL, NT, VM, bad RIP/RSP, bogus stack location, and excess code size.

## Deliberate limits / next gate

Single QEMU vCPU, trusted compile-time embedded HKEX only. No arbitrary ELF relocation, loading from disk, general user syscalls or pointers, robust side-channel/security sandbox, SMP, FPU/SIMD or FS/GS state, calibrated wall time, user-initiated cancellation, IPC, nested IRQ, UEFI, USB/keyboard/GUI, or physical PC. M5-E3 must still provide integrated stress/hardening and exact-head CI review, and M6 physical hardware cannot be assumed from these results. [Tracking Issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
