# M5-E3-D — contain an owned Ring3 timer IRQ with poisoned user stack

**Status:** actual QEMU BIOS, host UBSan proof PASS on a feature branch stacked on E3-C. New PR-head Actions/Gitleaks/merge **NOT YET VERIFIED**. Single CPU and only known compile-time HKEX images; not a complete secure arbitrary-code sandbox.

## Prior confirmed failure

In the existing opt-in M5-E2 periodic x2APIC environment, an independently assembled HKEX CPL3 program can set `RSP=0` using an ordinary register instruction and then spin indefinitely, without triggering any syscall or memory access. The real CPU still delivers the local x2APIC timer IRQ on trusted TSS.RSP0. Its saved **user** RSP is zero, so the existing strict user-IRET frame guard rejects it and **terminates the whole kernel** with `M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT` (QEMU exit 57). This was reproduced before the patch. A bad user register is not proof that the kernel's own interrupt stack was compromised.

## Narrow runtime change

- Keep the original **strict** M5-E2 normal timer IRQ-frame guard unchanged. All normal user IRQs continue to verify exact code RIP, user RSP bounds, interrupt frame, active CR3, selectors, and flags before the IRQ handler sends EOI and IRETQs back to the same user program.
- If the strict guard rejects a frame, the handler **fails closed unless a second independent, strictly bounded CPU/TSS/owner provenance check passes**. The same pure C ownership proof as M5-E3-C malformed `INT 0x80` verifies the exact saved **160-byte frame address** on trusted TSS.RSP0, CPL3 CS/SS, IF and other valid flags, current private CR3 matching the single six-frame user task, original distinct supervisor CR3 and saved shell stack, no previous task termination and active selected program. Crucially this proof **never accesses or relies on the corrupted user RIP or RSP**. Saved CS is checked before user-only SS/RSP fields to avoid interpreting a shorter CPL0 frame as Ring3.
- Only when independent CPU owner provenance passes does the timer send actual x2APIC EOI, emit `M5_E3_USER_IRQ_FRAME_INVALID`, retire the offending user task by the established no-return supervisor stack/CR3 handoff, reclaim all six owned frames and return the COM1 shell prompt with `M5_ERR_USER_TIMEOUT`. A real unowned/wrong-CR3/stale or kernel-mode IRQ remains fatal. Do not attempt `IRETQ` with the corrupted user stack.
- E3-D aborts malformed user frame on the **first** genuine IRQ; the existing normal four-IRQ count remains in force for a healthy nonyielding Ring3 program. The APIC count remains uncalibrated; no millisecond SLA claim.

## Actual guest and negative proof

```sh
python3 scripts/test_m5_user_bad_irq.py
python3 scripts/test_m5_user_timeout.py
python3 -m unittest tests.test_user_syscall_policy tests.test_user_timeout_frame -v
```

The positive test assembles **four independent, nonyielding actual CPU user programs**, each writing a malformed user RSP (null, code virtual page, kernel virtual address, or above the user stack) then spinning with no syscalls/yield. In **three separate real QEMU x86-64 BIOS boots**, the guest actually interrupts each one by the hardware x2APIC timer, logs `M5_E3_USER_IRQ_FRAME_INVALID`, frees six frames, sends a new COM1 prompt and successfully runs a **separately HTML-compiled, bounded ASCII text** HKEX app. It additionally expires one healthy nonyielding task via the *normal four-tick* path, and checks final HTML-derived kernel exit, no `M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT` and no frame leaks. Across the three guests: **12 corrupt-stack processes retired + 15 successful HTML user runs**. This is real native QEMU/COM1 evidence, not a fake timer or software replay.

The independent pure `user_syscall_policy.c` / `user_timeout_frame.c` native GCC UBSan O0/O3 policies reject forged CPL0 selectors, wrong owner/CR3, invalid kernel TSS.RSP0 frame pointer, missing task, broken flags and wrong kernel return context. Existing `scripts/test_m5_user_timeout.py` confirms masked real timer **cannot** make a nonyielding task appear to progress, and the same CPU without x2APIC fails closed. Legacy task/exception modes are unchanged by this opt-in E3-D switch.

## Known remaining failure and non-goals

This narrow repair covers **an actual delivered timer IRQ** from a CPU-verified active Ring3 task with a malformed saved user RIP/RSP. It does not change the legacy fail-stop semantics of unrelated M4 modes, kernel faults, wrong CR3, or missing owned frames. A user program that corrupts its RSP and triggers a **different exception** (#PF/#GP) before a timer tick can still encounter a stricter exception-frame guard and cause kernel fail-stop: that requires its own validated exception-origin ownership review. There is no arbitrary process authentication, ELF loader, SMP, FPU/FS-GS, nested IRQ, calibrated wall-time accounting, UEFI or physical hardware acceptance. The main M5 gate remains a bounded prototype, not a security certification. [Tracking Issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
