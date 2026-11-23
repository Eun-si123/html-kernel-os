# M4-D — actual x2APIC IRQ preemption of isolated CPL3 user tasks

**Verified locally on a single mini-PC QEMU x86-64 BIOS profile. Exact PR-head
CI and merge must be checked separately.** This is a bounded native acceptance
experiment, NOT a production process scheduler or complete OS.

## Native CPU behavior

The opt-in build enables --exception-idt --tss-ist --user-preempt-probe with
--test-exit for test status. Run in QEMU q35 -cpu qemu64,+x2apic -smp 1.

- 12 of the validated 16 USABLE owned frames contain two distinct private CR3
  PML4/PDPT/PD/PT roots, user RO code pages and RW stacks. Both tasks use the
  same virtual address but have distinct physical code/stack frames.
  Inherited kernel page entries are supervisor-only.
- Two independent ring0 16KiB IRQ kernel stacks accompany two CPL3 contexts.
  Real periodic local x2APIC IRQ 0x40 interrupts both tasks, which NEVER yield.
  Assembly saves all 15 GPRs and the real architectural CPU iret frame.
  The dispatcher checks current/target CPL3 state, CR3, TSS.RSP0, frame
  pointers and stack canaries before setting the new CR3 and TSS.RSP0,
  acknowledging the interrupt and returning through IRETQ.
- Both user payloads keep distinct known values in all 15 GPRs, checked in
  real CPU interrupt frames after their initialization. The user loops each
  increment their own physically isolated stack counter. Native evidence
  includes A0 B0 A1 B1 A2 B2, requiring actual user CPU progress.
- Once both have progressed, the kernel signals A via A's own user stack.
  A performs an unauthorized supervisor-address read, causing actual CPL3 #PF
  at exact CR2 0xFFFFFFFF80001000 and error 0x5 on the M3 IST2 stack.
  The exception checks current root/selector/RIP/RSP/IF/fault address/error
  and prior progress. The IRQ is masked and the CPU returns to the trusted
  original kernel stack and CR3 before reclaiming A's six frames.
- The surviving B user resumes its saved CPL3 IRQ frame under its own CR3,
  makes further CPU progress, and issues DPL3 INT 0x80 to exit. B's six
  owned pages are reclaimed, frame-owner live count is zero and the HTML-
  generated kernel executes with QEMU success exit code 33.

## Validation

    python3 scripts/test_m4_user_preempt.py
    python3 -m unittest tests.test_user_preempt_policy -v

The real QEMU suite covers three repeated boots, changed HTML -> changed ISO
and real CPU output, and the following negatives:
- Missing x2APIC/disabled APIC => guest error exit 57.
- Forged ring0 selector and duplicate task CR3 => guest error exit 57.
- Unexpected A page fault at different CR2 => genuine #PF, error 0x5,
  guest exit 45; not falsely recovered.
- Unexpected survivor B #PF => genuine fail-stop, exit 45.
- Masking the timer => no task interleaving, bounded host timeout.
- Unsupported/incompatible command-line flags => no boot ISO produced.
- Native GCC -O0/-O3 UBSan policy tests reject wrong CPL, IF, RIP/RSP, CR3,
  fault type/address/task and insufficient progress. Previously merged
  M1/M3/M4-A/B1/B2/C1/C2 tests must remain green in exact-head CI.

## Explicit limitations

One QEMU BIOS virtual CPU only. Local APIC counter not calibrated. FPU/SIMD
state, FS/GS bases, nested IRQ, SMP, PCID, LA57, hardware/UEFI, user ELF/HTML
dynamic loader, arbitrary user programs, general syscalls and filesystem are
NOT supported. Both user payloads are fixed trusted assembly test images.
This is a restricted QEMU M4 proof, NOT production-grade process security or
a usable operating system; M5 console/readonly init FS/program execution
and M6 physical machine safety remain future work.
