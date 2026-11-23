# M4-D — real x2APIC preempted CPL3 tasks and survivor fault handling

**Local native QEMU proof: PASS. Independent GitHub CI/head must be checked before merging.**

## Real execution (opt-in, experimental)

Option --exception-idt --tss-ist --user-preempt-probe builds a distinct ISO.
Actual Limine BIOS x86-64 kernel allocates two independent private CR3
trees, each with 4KiB user executable (read-only) code and a writable 4KiB
user stack, using existing bounded tagged 16-frame allocator (12 claimed).
Each task receives its own trusted 16KiB CPL0 interrupt stack.
TSS.RSP0 is updated to the selected stack **before** IRET to ring3;
task switches reload separate CR3, flushing TLB without PCID.

CPU x2APIC local periodic timer vector 0x40 interrupts ring3 loops that
**never yield**, invoke syscalls, HLT or blocking I/O. Assembly handler
preserves all 15 GPRs and hardware IRQ RIP/CS/RFLAGS/RSP/SS, calls checked
dispatcher, restores task interrupt stack, and IRETQ resumes CPL3.
Spurious vector 0xff uses IRETQ without EOI; timer IRQ sends proper EOI.
Emulator-specific count 1,000,000 / 16 is **not calibrated 100Hz**.

Guest writes continuously to its private user stack counter. Each IRQ
checks physical HHDM value genuinely increased, user CS/SS/RIP/RSP/IF/IOPL,
four register sentinels, kernel-stack bounds/canary, task CR3, TSS.RSP0.
Sequence is A0/B0/A1/B1/A2/B2. Kernel then arms A private user flag.
A makes actual illegal CPL3 read -> #PF error 5 with exact expected CR2.
IST2 handler checks user fault, restores original CR3 and releases A only,
then resumes independent B saved user context/CR3. B progresses two times
afterwards. Timer masks, main stack/CR3 restored, B frames reclaimed.
Original HTML-generated native kernel then runs.

## Reproduce and expected evidence

    python3 scripts/test_m4_user_preempt.py
    python3 scripts/build_boot.py --exception-idt --tss-ist --user-preempt-probe --out build/html-kernel-m4-user-preempt.iso

QEMU profile: -M q35 -cpu qemu64,+x2apic -smp 1 -m 256M, BIOS.
With --test-exit, exact native marker sequence and exit 33 include:
M4_D_A_CPU_PF_5, M4_D_A_RECLAIMED, M4_D_B_AFTER_FAULT_3,
M4_D_B_AFTER_FAULT_4, M4_D_RING3_PREEMPT_PASS, M4_D_NO_FRAME_LEAK,
then changed-source HTML kernel output.

## Negative controls

- Three consecutive actual QEMU boots, strict progress order and exit 33.
- HTML changed -> distinct ISO and observed native output.
- A privileged port IO -> #GP(0), or RO-code store -> #PF(7): B survives.
- Misaligned saved CPL3 IRQ context rejected before use, exit 55.
- Unsupported x2APIC CPU profiles rejected, exit 55.
- Masked real timer prevents transfer from non-yielding A, host timeout.
- Unexpected B #GP fails entire guest with exit 45; never mis-recovers.
- Incompatible builder options fail without producing ISO.
- Host UBSan GCC -O0/-O3 validates 160-byte ABI frame offset and
  fabricated selectors, IF/IOPL, user ranges and register negative cases.
- Independent M1/M3/M4-A/B1/B2/C1/C2 QEMU regressions remain required.

## Explicit limitations

Bounded **two trusted tasks, single vCPU, QEMU** native proof, NOT a
general-purpose production scheduler/security boundary. No arbitrary
user binary loader, HTML-to-CPL3 task creation, syscall under concurrent
live preemption, user pointer copy, dynamic task creation, calibrated timer,
FPU/SSE/FS/GS preservation, nested IRQ, SMP or multicore TLB shootdown.
No general-purpose framebuffer/keyboard/console input, FS, UEFI or real PC.
User stack NX not enforced. Keep normal HTML boot and browser demo unchanged
as opt-in build is isolated. M4 bounded experiment passed locally; **full
M4 milestone OPEN** pending reusable process lifecycle/security acceptance
and exact-head independent CI evidence; M5/M6 still pending.
