# M5-E3-I — real CPL3 #DB/#BP after user corrupts its own stack pointer

**Scope:** only a known, currently owned Ring3 executable in an opt-in
interactive guest. Real QEMU and GCC UBSan host negative gates below.
Exact GitHub PR-head CI, Gitleaks, merge and physical PC evidence are
independent milestones. This does **not** secure arbitrary ELF or SMP.

## Confirmed existing fatal error

A separately assembled HKEX user program can run `xorq %rsp,%rsp` and
`.byte 0xf1` (ICEBP, CPU #DB vector 1) or `.byte 0xcc`
(INT3, CPU #BP vector 3). With merged M5-E3-H main, a real q35 BIOS
QEMU native boot delivers the expected CPU vector, saving
`RIP=0x0000400000000004` for the 4-byte image, then the original
strict normal user-stack guard rejects the intentionally corrupted RSP
and kills the **whole** guest with QEMU exit **45** before any timeout.

These *trap-class* exceptions differ from faults: the saved CPU RIP
typically points **after** the trap opcode, including exactly
**one-past the last byte** of a loaded program. They push *no* CPU error
word, so their exact CPL3→CPL0 CPU frame is five qwords:
RIP, CS, RFLAGS, user RSP, SS at trusted **TSS.RSP0 − 40**. They are
**not** the six-word #GP/#PF error-code frames or the 160-byte x2APIC
interrupt/syscall snapshots.

## Narrow owner-only recovery

- Original strict `htmlk_m5_accept_user_fault` runs **first**.
  The new fallback exists **only** for the two known no-error-code
  trap vectors #DB(1)/#BP(3) when their saved CPL3 RSP was corrupted.
- `htmlk_m5_bad_trap_stack_owned` validates the precise 40-byte
  CPU frame at trusted TSS.RSP0−40 and reuses the full strict active
  task/CR3/supervisor-stack/CS/SS/RFLAGS/six-page/code-bound policy.
  To account for trap-class RIP only, when saved RIP is **exactly
  one-past-code-end**, the function checks a **local copy** with
  RIP decremented by one. It does not adjust CPU state or return into
  the corrupted program. RIP more than one byte past end is rejected.
- A valid user RSP does not qualify for the fallback. An unowned
  process, wrong/old CR3, wrong CPU frame, unexpected CPL0 selector,
  wrong IF or RFLAGS, stale termination state and a kernel exception
  retain the existing fatal behavior.
- On proof the selected app only is retired, distinct genuine CPU
  markers `M5_E3_USER_DB_BAD_RSP_RETIRED` or
  `M5_E3_USER_BP_BAD_RSP_RETIRED` are emitted, then the existing
  **no-return** trusted supervisor CR3+kernel RSP handoff reclaims
  the owned six pages and returns to the still-running COM1 prompt.
  No user pointers are read.

## Actual QEMU and GCC UBSan evidence

```sh
python3 -m unittest tests.test_user_fault_policy -v
python3 scripts/test_m5_user_bad_trap_stack.py
```

- Pre-fix actual q35 BIOS x2APIC QEMU: corrupted RSP + genuine
  #DB and #BP both fatal exit 45, real CPU vectors 01/03 and saved
  RIP exactly code-end, no prompt.
- After fix, no-timer guest: genuine #DB, #BP and the separately
  encoded **two-byte** `int $3` trap with poisoned user RSP all
  retire safely, followed by three healthy HTML user program reruns.
- Real one-vCPU x2APIC: **three complete BIOS QEMU boots** each
  execute five different bad-RSP trap images (#DB ×2, #BP ×3),
  six successful independent native HTML user reruns and one real
  nonyielding program stopped by the actual x2APIC timer.
  All cases check real E9 debugcon and UART bytes, exact task frame
  reclamation, next-prompt survival and successful kernel final exit.
- Legacy standalone M5-C1 QEMU remains fatal exit45 for both trap
  classes (#DB vector1; software INT3 on its DPL0 IDT is rejected
  by CPU with #GP vector13). This is an explicit negative control.
- GCC UBSan O0/O3: only vectors 1/3 accepted, valid exact TSS frame,
  right code-end bound, CPL3 CS/SS, expected IF, active private CR3,
  six current pages and bad user RSP; forged/old/valid-stack owner
  and frame-displacement cases are denied. Previous #UD/#DE/#GP/
  #PF/IRQ and syscall fault isolation are separate regressions.

## Deliberate remaining limitations

This is an *opt-in, one-vCPU, trusted bounded-image* demonstration.
It does not promise safe arbitrary app execution, general CPU debug
register/TF semantics, FPU/FS/GS save/restore, SMP, UEFI, physical
hardware, authenticated executable images or a calibrated timer.
The browser live ISO is a **no-x2APIC deadline** build, whereas
these timer experiments are **native QEMU only**. The compiled
HTML-shaped source language is not standard browser HTML executed
directly on the CPU. Tracking issue
[M5-E #75](https://github.com/Eun-si123/html-kernel-os/issues/75)
and [bad stack #91](https://github.com/Eun-si123/html-kernel-os/issues/91).
