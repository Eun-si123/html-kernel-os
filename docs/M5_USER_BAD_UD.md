# M5-E3-E — contain an owned Ring3 #UD after the user corrupts RSP

**Status:** local genuine QEMU and UBSan proof PASS; **PR #94 exact-head GitHub QEMU Actions `45145677104`/`45145738649`, Gitleaks `45145738754` PASS and merged as `b4628d7`**. The separate E3-F #DE follow-on remains gated by its own PR-head verification. This is a **very narrow opt-in exception recovery gate**, not arbitrary-code security certification.

## Confirmed pre-fix kernel liveness defect

A separately assembled, valid bounded HKEX Ring3 executable can run `xorq %rsp,%rsp; ud2` (with **no syscall and no memory dereference**). The CPU correctly delivers #UD vector 6 on the privileged TSS.RSP0 stack, saving an architectural **five-qword** RIP/CS/RFLAGS/RSP/SS frame. But the existing M5-E1 exception guard assumes the *saved user RSP* is within its allocated user-stack page; it rejected this exception, followed the supervisor fatal path, and killed the entire interactive QEMU kernel with **actual QEMU exit 45** and `M3_EXCEPTION V=06`. The M5-E3-D real timer interrupt workaround does not apply: #UD is triggered **before** the next timer tick. This failure was reproduced independently on the original merged main `162aa4c` before implementing the fix.

## Narrow CPU/task ownership proof before recovery

The original **strict** M5-E1 ordinary user exception-frame guard remains unchanged. In `boot/exception_idt.c` vector 6 **only**, if the strict guard fails, the handler first checks the CPU's saved CS is CPL3 before reading any user-only RSP/SS field. The second-chance pure policy `htmlk_m5_bad_noerr_stack_owned()` verifies (renamed by the subsequent E3-F shared no-error-code fault policy):

- Actual CPU-provided five-qword exception frame pointer is **exactly** TSS.RSP0 − 40; TSS.RSP0 is a 16-byte-aligned high canonical supervisor pointer. The 160-byte syscall/x2APIC IRQ frame is explicitly not interchangeable with this #UD frame.
- Saved exact CPL3 CS=0x2b, SS=0x33, valid reserved RFLAGS, the expected IF state of this opt-in mode, and no IOPL/NT/VM impersonation. The saved user RIP must still be **inside the validated loaded executable** (not past its code end), rather than freely trusting the user-code address.
- The running CR3 matches the one owned private page root, is aligned and distinct from a saved supervisor CR3, six task-owned physical frames remain live, there is a nonzero high-canonical saved supervisor stack, a selected active process and **no prior fault/exit/timeout/invalid-syscall retirement**.
- **Only** a CPU-saved user RSP *outside* the known private user-stack interval may use this fallback. A normal valid-stack #UD must still be handled through the original strict policy. No arbitrary user pointer or broken user stack address is accessed, copied or used for IRETQ.

After all guards succeed, only the offending user task is marked faulted, `M5_E3_USER_UD_BAD_RSP_RETIRED` is logged, the original trusted supervisor CR3 and kernel main RSP are restored by the existing no-return handoff, and the six task-owned pages are reclaimed **before** the COM1 shell reports `M5_ERR_USER_FAULT` and receives further commands. Kernel-origin, malformed selector/CR3/TSS-frame, unowned/stale-task, or other unrecognized CPU exceptions remain **fatal**. No blanket exception swallowing, timing shortcut or new generic syscall capability.

## Verifiable native evidence

```sh
python3 -m unittest tests.test_user_fault_policy -v
python3 scripts/test_m5_user_bad_ud_stack.py
```

- On actual unpatched QEMU the genuine `RSP=0`/`UD2` scenario produced `M3_EXCEPTION V=06`, guest exit **45** and **no prompt**. After the change, the same scenario returns to `M5_PROMPT>` with a validated process reclaim and a successful independently compiled HTML user program rerun.
- Three complete QEMU q35 BIOS boots with x2APIC enabled: **four independent hostile code images** corrupt user RSP to zero, executable code address, supervisor kernel address or beyond the user-stack upper bound and each performs real `UD2`. The guest recovers all four known-task CPU faults and runs **five** successful HTML-compiled text programs per boot. A real nonyielding user task also expires via a genuine fourth x2APIC interrupt; every execution has separately checked E9 debugcon/COM1 output and correct six-frame reclaim markers. The same corrupted-RSP #UD recovery works without a timer in the E1 mode.
- An old standalone **M5-C1**, without the opted-in fault recovery, still exits QEMU with **45** and true `M3_EXCEPTION V=06` for corrupted-RSP #UD. GCC UBSan `-O0/-O3` pure policy unit tests reject forged CPL0 selectors, frame displacement (including confusing 160-byte syscall frames with 40-byte exceptions), wrong or reused CR3, TSS stack, invalid RFLAGS/IF, code RIP past bound, owner missing, wrong page count, valid user RSP, and already-retired task states. Existing M4-D/M5-E1 and M5-E3-D x2APIC tests form regression guards.

## Important limits and next gate

Only known active opt-in Ring3 **#UD with poisoned user RSP** is newly recoverable. Corrupting RSP and then triggering **#GP, #PF, #DE, #DB, or #BP** remains a separate unverified case; especially page fault IST2 requires its own frame/stack provenance, so this policy cannot simply be copied onto other vectors. FPU/XSAVE, FS/GS, SMP, nested CPU faults, general ELF/untrusted image integrity, process groups, calibrated timing, UEFI and physical hardware are **NOT RUN/NOT SUPPORTED**. The user-program byte checksum is not a signature. The phase belongs to [M5-E tracking issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).

## Follow-on (separate M5-E3-F phase)

This initial E3-E contract covers #UD only. The subsequent opt-in E3-F patch generalizes the same five-qword frame/owner check to the only other supported *fault-class no-error-code* vector **#DE (0)**, while keeping #UD (6) acceptance unchanged and excluding all other vectors. See [M5-E3-F CPU divide error evidence](M5_USER_BAD_DE.md); its exact PR-head CI/merge is independently gated.
