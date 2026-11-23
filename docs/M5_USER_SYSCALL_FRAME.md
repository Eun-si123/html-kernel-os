# M5-E3-C — contain malformed Ring3 syscall return frames

**Status:** local genuine BIOS QEMU/host UBSan PASS; exact PR-head GitHub CI, merge, arbitrary-untrusted-code security and physical PC remain **NOT YET VERIFIED**. Follows the merged E3-B user trap containment and merged F1 HTML user compiler.

## Reproduced native bug before the change

A relocation-free assembly HKEX program used only ordinary CPL3 register instructions to write the address of its executable code page into `RSP`, then called `INT 0x80`. QEMU's CPU correctly switched to the trusted kernel TSS.RSP0 stack and saved that poisoned user RSP. **Before the fix**, the kernel rejected the return frame with `M4_BAD_RING3_SYSCALL_FRAME` and exited QEMU with **code 53**, destroying the live COM1 shell despite `--user-fault-recover`. This was a confirmed process-isolation availability gap, not an attack against a machine outside the local emulator.

## Narrow fix

- The valid syscall ABI is **unchanged**. Normal syscalls still require exact CPL3 CS/SS, canonical RIP/RSP in the declared executable/stack region, the current private CR3 and IOPL0. Bad IDs/arguments already terminate only the known process (E1, merged #78).
- If the syscall frame fails validation, the new `boot/user_syscall_policy.c` gate can retire **only** the *currently owned* user task. It checks the exact 160-byte saved CPU/15-GPR frame location relative to the actual trusted TSS.RSP0 stack, CPL3 selectors, valid reserved RFLAGS/IOPL/NT/VM, active private CR3 and original distinct supervisor CR3, saved original kernel stack, active selected app, exactly six live owned physical frames and no completed termination. It does **not read or dereference** the user-supplied RIP/RSP: those are *the fields being rejected*.
- The saved CS is read **first**. A CPL0-origin interrupt has a shorter interrupt frame; the code never accesses nonexistent saved user SS/RSP fields in that case. Wrong owner/CR3/stack frame, forged selectors or a kernel-origin syscall remain **fail-stop**. Recovery does not trust arbitrary pointers or repair unrelated kernel faults.
- If the independent origin gate passes, the existing trusted `htmlk_m4_user_return()` restores original supervisor CR3 and kernel stack, releases all six physical frames via the established E1 ownership path, reports `M5_E_USER_BAD_SYSCALL_FRAME` and `M5_ERR_USER_SYSCALL`, and returns to the real live COM1 command prompt. It is not a mechanism to resume code with a corrupted user stack.

## Actual native tests and negatives

```sh
python3 -m unittest tests.test_user_syscall_policy -v
python3 scripts/test_m5_user_syscall_frame.py
```

`scripts/test_m5_user_syscall_frame.py` boots **four independent real QEMU q35 BIOS guests**, two without active periodic IRQ and two with x2APIC timer. Each real guest runs five independent user HKEX programs, with user RSP set to zero, user code address, kernel virtual address or above the mapped stack, or with an `INT 0x80` at the last byte of the executable (where the CPU saves one-past-end RIP). Every invalid invocation retires *only* the one program, frees its six frames, then the same guest boots a separately **HTML-compiled** good HKEX app that reports `2026`. It asserts five matching errors and five successful reruns **per boot**, COM1 TX/debugcon output and HTML-derived kernel exit 33. A standalone older M5-D1 guest proves original fatal rejection (exit 53) remains when the opt-in fault recovery is disabled. One additional actual QEMU boot builds the merged F2 **HTML text** user program, then interleaves **three successful checked-code-page string outputs**, a malformed user syscall frame, a forbidden user string pointer, and a genuine x2APIC nonyielding-app timeout, proving these two distinct user syscall guards and page ownership compose in the same guest. The builder still strictly enforces the original 16-file ROMFS cap: this mixed experiment creates a minimal input tree with only the two additional negative images, not the entire unrelated fixture set.

Host GCC UBSan -O0 and -O3 tests reject forged ring0 selectors, wrong saved stack frame address, invalid TSS.RSP0 canonicality/alignment, mismatched or unaligned CR3, corrupt RFLAGS, no active program, stale/double-terminated frame registry, absent kernel return context. The old M4-C1/M5-C1 syscall rejection and M5-E1/E2 existing normal/error paths must remain unaffected, verified by their native QEMU regression scripts in the PR.

## Deliberate limitations / next safety gate

This guard handles **a delivered syscall** from one recognized Ring3 program. It does **not** guarantee that *all* possible malicious user state will be safely retired. In particular, a program that writes an invalid RSP and then spins indefinitely may be interrupted by the existing M5-E2 timer while the timer's stricter IRQ-frame RSP guard fails closed, killing this experimental kernel; separate timer-origin containment is future E3 work. No general ELF, user pointer copyin/copyout, syscall ABI, arbitrary process authenticity, SMP, FPU/FS/GS, nested IRQ, calibrated wall-time quota, real hardware or UEFI. [M5 integration issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
