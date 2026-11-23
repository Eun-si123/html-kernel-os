# M5-E3-D — real Ring3 `INT 0x80` at the final HKEX instruction

**Status:** opt-in `--user-fault-recover` boundary repair, Ubuntu mini PC actual QEMU proof PASS locally. Exact PR-head CI/merge, physical PC, or broad untrusted-program safety are NOT claimed until verified independently.

## Confirmed kernel liveness bug

The x86-64 `INT 0x80` interrupt gate saves an **instruction-return RIP** after the completed software interrupt, just as `INT3` does. If that `INT 0x80` is the **last instruction of a verified relocation-free HKEX program**, saved RIP is **exactly** the end of the program's declared byte length. Prior `boot/user_probe.c` rejected all `RIP >= code_end` as `M4_BAD_RING3_SYSCALL_FRAME`; a real user-program `mov $99, %rax; int $0x80` ended the entire **native COM1 kernel shell** (actual QEMU error exit 53) even though `--user-fault-recover` was on. A valid user program whose final instruction was a legitimate `exit` syscall was also incorrectly rejected.

## Fix and trust boundary

Only when `HTMLK_M5_USER_FAULT_RECOVER` is defined, the strict CPL3 syscall dispatcher accepts the one architectural boundary `saved_rip == code_base + verified_code_length` as a *candidate*. All existing saved CPU frame CPL3 CS/SS, canonical address, user stack, owned current CR3, IOPL, process state, six-frame ownership and original safe kernel return stack checks remain effective. At this boundary:

- A **correct terminating syscall** (`rax=1`, `rdi=0`, previous stack handshake and exactly one successful report, and not already exited) is permitted. This syscall does not resume at the non-executable EOF address: it switches to trusted original kernel CR3/stack and releases all six owned frames.
- An **unknown or nonterminating syscall at EOF** aborts the **offending user program** only. It never IRETs to the byte past the verified executable. The process emits `M5_E_USER_EOF_SYSCALL_REJECTED`, follows the existing M5-E1 original-kernel-CR3/stack and six-frame reclaim path, prints `M5_ERR_USER_SYSCALL`, and a genuine COM1 prompt accepts the next command.
- Any RIP *past* code end, a wrong user CS/SS/stack or an invalid current CR3 is **not exempted**; the existing fail-closed policy continues to apply. The old M4-C1 and standalone M5-C1 without guarded recovery retain strict *fail-stop* behavior, including for a legitimate terminating syscall at EOF. This does not provide arbitrary user pointer handling.

The fix is compatible with the separate M5-F2 user text syscall (checked read-only code pointer) and existing x2APIC timer expiration, without changing any syscall IDs or user page permissions.

## Reproduce actual native guest evidence

```sh
python3 scripts/test_m5_user_syscall_eof.py
python3 scripts/test_m5_user_fault_recovery.py
python3 scripts/test_m5_user_timeout.py
python3 scripts/test_m5_html_user_text.py
```

`scripts/test_m5_user_syscall_eof.py` assembles **three independent, genuine x86-64 user payloads**: unsupported syscall ID at EOF, recognized numeric report syscall at EOF (must **not** resume beyond code bounds), and valid full handshake+report+exit syscall **exactly** at EOF. It also supplies an independent healthy program and, in the text mode, a separately compiled HTML string program. In **three modes** — no timer, real x2APIC timer, and real x2APIC plus M5-F2 HTML-derived ASCII text — each guest boots **twice** and executes valid user → two EOF-invalid programs → valid re-runs → valid EOF exit → valid re-run → (if enabled) real nonyielding timer timeout → clean kernel HTML exit. Both actual COM1 UART output and E9 debugcon must match exact event and reclaim counts. **Six actual QEMU BIOS boots** plus separate legacy M5-C1 BIOS builds for each payload verify the implementation; the unsupported `INT80` programs must never bring down the shell again.

## Limits / next gate

The program format remains a bounded build-time-trusted HKEX user page, not ELF, unsigned general external program loading or arbitrary user pointer/syscall processing. One x86-64 QEMU vCPU, no XSAVE/FPU/FS-GS/SMP, no UEFI or actual physical PC evidence and no calibrated wall-clock quota. Other malformed syscall frames are handled by the independent M5-E3 syscall provenance policy (PR #87); verify both policies together on the same exact commit and re-run true QEMU, not just unit tests, before merge. Track [M5-E issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
