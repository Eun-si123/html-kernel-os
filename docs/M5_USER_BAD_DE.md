# M5-E3-F — contain a real Ring3 divide error with a poisoned user RSP

**Status:** local native QEMU + GCC UBSan proof PASS on a branch based on prior M5-E3-E. The exact PR-head GitHub Actions/Gitleaks result and merge have **NOT** been checked yet. Only a known, owned user program; never treat this as a general arbitrary-code sandbox.

## Proven fatal bug before the fix

Even with the narrow E3-E poisoned-stack #UD recovery, a separately built Ring3 executable could set its stack pointer to zero, execute `DIVQ` with divisor zero, and trigger an actual CPU **#DE vector 0**. The existing strict fault handler rejected this saved bad user RSP and killed the native QEMU kernel (status **45**, `M3_EXCEPTION V=00`). This was reproduced with a real BIOS QEMU guest prior to the follow-on patch. The earlier M5-E3-D x2APIC fix cannot help because the divide error occurs **before** any timer interrupt.

## Minimal second-chance ownership proof

Both **#DE (0)** and **#UD (6)** are *fault-class* CPU exceptions **without an error-code word**. With CPL3→CPL0 stack switching, the CPU saves precisely five qwords (RIP/CS/RFLAGS/RSP/SS), not the 160-byte 15-GPR syscall/IRQ frame and not the error-code stack layout used by #GP/#PF. This PR generalizes E3-E's existing pure `htmlk_m5_bad_noerr_stack_owned()` policy; it does not add a second parallel state machine or interrupt handler.

- Only vector **0 or 6** may enter this owner-verified fallback (`htmlk_m5_bad_noerr_fault_vector` has exhaustive 0..31 host negative tests). Other vectors, including *trap-class* #DB/#BP whose saved RIP has different semantics, or error-code #GP/#PF, retain their existing strict handlers.
- The existing strict fault guard runs **first**. Only if it rejects a true CPL3 frame due to a *poisoned saved user RSP* can the independent CPU/TSS/CR3/ownership guard consider termination. It validates the exception frame address as **exactly TSS.RSP0−40**, canonical supervisor-stack position, CS/SS, expected RFLAGS IF, code RIP strictly inside the loaded verified HKEX image, live private aligned CR3 distinct from the saved supervisor CR3, six owned pages, active selected program, saved trusted supervisor RSP, and no previous termination. A valid user stack never qualifies for fallback.
- After proof the caller marks **only** this program faulted, restores original CR3 and supervisor main RSP via the existing `htmlk_m4_user_return()`, reclaims all six owned frames and then reports `M5_ERR_USER_FAULT` to the same live COM1 shell. Only the marker differs (`M5_E3_USER_DE_BAD_RSP_RETIRED` for vector 0, existing `M5_E3_USER_UD_BAD_RSP_RETIRED` for vector 6). Nothing dereferences the corrupted user RSP. Genuine CPL0/ownerless/forged privilege frames remain fatal.

## Native acceptance and denial tests

```sh
python3 -m unittest tests.test_user_fault_policy -v
python3 scripts/test_m5_user_bad_ud_stack.py
python3 scripts/test_m5_user_bad_de_stack.py
```

`scripts/test_m5_user_bad_de_stack.py` independently assembles four genuine x86-64 Ring3 binaries, each poisoning RSP to a different value (zero, code page, kernel address, or beyond user stack) before the same actual `DIVQ` instruction raises CPU #DE. Three complete BIOS QEMU x2APIC boots each recover **four #DE tasks** and successfully launch **five** distinct HTML-built text output processes with correct COM1/E9 bytes and six-frame cleanup. Each boot additionally executes a nonyielding user task terminated only by the actual x2APIC timer, demonstrating the original timeout path remains valid. A separate QEMU boot **without** timer proves native #DE owner recovery does not depend on a fabricated IRQ, and the older M5-C1 nonrecovery mode still fails with the real CPU #DE exit 45. The original E3-E #UD suite is rerun against the generalized policy to prove its original acceptance has not regressed.

Host GCC UBSan `-O0/-O3` validates the shared pure CPU ownership policy, including rejecting kernel-mode CS, forged selectors/SS, wrong or displaced 40-byte CPU frames, 160-byte IRQ frames, wrong CR3, stale frames/owner, invalid IF/flags, invalid code RIP, malformed supervisor RSP, valid user RSP, and every vector other than #DE/#UD. The default boot artifact and standard non-user HTML kernel compiler targets remain unaffected.

## Deliberate limits

**Not** a universal exception fix: a poisoned RSP followed by #GP/#PF/#DB/#BP has distinct error-code/IST or trap semantics and is still outside this accepted recovery path. No arbitrary untrusted executable/authenticity guarantee, user pointer syscall copyin/out, SMP, FS/GS, FPU/XSAVE, UEFI, calibrated timer or physical PC evidence. The code's FNV checksum is not a cryptographic signature. E3-E is merged as PR #94 (`b4628d7`); this E3-F proof remains a separately gated additive, testable phase linked to [M5 issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
