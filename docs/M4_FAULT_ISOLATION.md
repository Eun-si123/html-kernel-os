# M4-C2 — isolated Ring 3 fault survival (real QEMU, bounded)

**Evidence:** native Ubuntu mini-PC QEMU BIOS and GCC UBSan PASS in this
branch. Exact PR-head GitHub Actions and merge status are tracked separately.
**This does NOT mean M4 is complete or user processes can run concurrently.**

## The real CPU execution path

The new opt-in mode is:

    python3 scripts/build_boot.py --exception-idt --tss-ist --user-isolation-probe --out build/m4-isolation.iso

On QEMU q35, single vCPU with 256 MiB, two **different fixed privileged
kernel-owned** user payloads are copied into two distinct memory images:

- Two separate PML4/PDPT/PD/PT roots, one code and one stack page each.
  Twelve actual 4KiB pages come from the existing 16-frame, USABLE-only
  owner-tagged M3 physical pool. Root CR3 and code/stack frames are distinct.
- Both use the **same canonical user virtual code/stack addresses**; CPU
  switches to a different CR3, which flushes non-global address translations
  because this probe explicitly refuses LA57/PCID configurations.
- Code is present, user-readable/executable, **not writable**. Stack is
  user read/write. Inherited bootloader kernel PML4 entries are U/S cleared.
  The Limine original PML4 is not modified.
- Program A writes 0x1111 to its private user stack, proves an INT0x80
  syscall from CPL3, then triggers a **real CPU fault**, not a software
  callback. Under #PF, the M3 IST2 emergency kernel stack is observed.
- Exception handling only accepts A's **exact** expected CPU vector,
  error code and fault address, CPL3 CS/SS, in-range user RIP/RSP, and
  corresponding active CR3. For unrecognized faults, the preexisting
  fail-stop M3 handler runs instead.
- Upon accepted fault, the kernel abandons the untrusted user context,
  restores the original kernel CR3 and saved main stack using the C1
  assembly return mechanism, then reclaims **only A's six owned frames**.
  The survivor's six frames remain allocated and untouched.
- Program B runs from its own CR3. Its same virtual stack address is
  initially zero (A's 0x1111 must not leak), then it writes 0x2222,
  performs INT0x80 and executes an explicit exit syscall. Kernel restores
  original CR3, reclaims B's six frames, asserts **zero live frames**,
  and then executes the exact generated HTML kernel source.

This is **sequential protected task execution with fault containment**.
No timer IRQ/preemption occurs during C2, and no general concurrent
userland scheduler is installed. Programs are fixed trusted test bytecode
copied from the kernel assembly, not untrusted HTML applications.

## Reproducible acceptance and rejection tests

    python3 -m unittest tests.test_isolation_policy -v
    python3 scripts/test_m4_isolation.py

The second script builds real BIOS QEMU ISO images with test-exit enabled
and checks exact native CPU debugcon output, QEMU exit code and source
provenance. Acceptance cases:

1. Default: A's CPL3 read of kernel supervisor address
   0xFFFFFFFF80001000 triggers **#PF error 0x5** and the real IST2.
   A-only cleanup occurs; B still syscalls and exits; native HTML kernel
   output follows. Three full BIOS boots assert the exact event order.
2. Alternate A privileged port OUT causes **#GP error 0**, B survives.
3. Alternate A writes to own read-only code causing **#PF error 0x7**
   at the known virtual code page, B survives.
4. Original HTML changed and rebuilt ISO differs, and exact changed
   text appears **only in the new ISO's real CPU output**.
5. The host-native policy test checks valid PF5/PF7/GP and rejects
   wrong process, vector, selector, stack, RIP, CR3, CR2, error,
   unsupported fault configuration and 4KiB image bounds under
   GCC -O0 and -O3 with UBSan.
6. A synthetic forged ring-0 exception context is rejected before CPU
   execution, with **non-success exit 55**.
7. A separate QEMU image faults in program **B**; the A-only escape path
   MUST refuse to recover B, and M3 reports genuine #GP with
   **non-success exit 45**. No false success marker or HTML output.
8. Missing IDT/TSS, concurrent M4-B2 preemption, other incompatible
   experiments and conflicting flags are rejected by the builder before
   creating an ISO.

## Remaining limitations / M4-D gate

- **No concurrent CPL3 scheduling, preemptive user processes or dynamic
  process creation.** M4-B2 x2APIC IRQ scheduling and M4-C2 ring3 fault
  isolation remain independent probes and intentionally cannot be combined.
- No FPU/SIMD, FS/GS, per-process TSS.RSP0 switching, thread state,
  SMP or multi-core TLB shootdown, calibrated timer, user loader,
  unrestricted syscall ABI, safe user-pointer copy, kernel heap,
  NX-enforced stack or arbitrary compiled HTML user programs.
- User faults are handled only for *one exact privileged-access class
  in a fixed known test task*. All unexpected faults correctly fail-stop.
  General kernel-mode faults remain fatal.
- No physical-machine or UEFI execution has been verified. QEMU proof
  must never be described as production-grade security isolation.

The next gate is **M4-D / user-mode timer integration**: genuinely
preemptive user tasks with distinct CR3, TSS.RSP0 switching and IRQ stack
ownership, preserving full user CPU context and handling faults while an
independent task survives. Per-task resource ownership, syscall copyin/
copyout, NX/guard pages and parallel safety require explicit later proof.
