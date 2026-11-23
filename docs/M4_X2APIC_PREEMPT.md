# M4-B2 — x2APIC timer preemption (native QEMU, opt-in)

**Status: mini-PC QEMU PASS; merge and exact-head GitHub CI evidence must be checked.**
This is an intentionally restricted **one-shot native proof**, not a reusable
multitasking kernel or completed M4 user-isolation milestone.

## What actually executes

- Single x86-64 virtual CPU, QEMU q35 with explicit qemu64,+x2apic.
- CPUID/APIC-base MSR checks before enabling x2APIC MSR mode.
- Local x2APIC periodic timer at vector 0x40; no external IOAPIC/PIC IRQ.
- A dedicated vector 0xFF spurious-interrupt gate returns with iretq
  without an unnecessary EOI (preventing a missing-IDT-gate fault).
- Dedicated 16 KiB kernel stack for each of two ring-0 tasks. Both execute
  busy loops **without** a software yield or scheduler syscall.
- The assembly timer ISR saves **all 15 general-purpose registers**, retaining
  the CPU's architectural interrupt frame, calls bounded C dispatch, restores
  another task's saved IRQ stack and returns with iretq.
- An APIC EOI precedes each return; the last IRQ masks the timer, acknowledges
  the interrupt and returns to the saved main kernel stack. Normal HTML-
  generated kernel code then runs and produces its exact expected output.
- Each task receives exactly three progress grants; strict A0 B0 A1 B1 A2 B2
  plus a minimum of five real task switches and checked counts must precede
  the final success marker. A limited tick budget rejects accidental deadlock.

## Reproducible commands

    python3 scripts/test_m4_preempt.py
    python3 scripts/build_boot.py --exception-idt --preempt-probe --out build/html-kernel-m4-preempt.iso

For the latter test ISO, boot with a single virtual CPU, for example:

    qemu-system-x86_64 -M q35 -cpu qemu64,+x2apic -smp 1 -m 256M -cdrom build/html-kernel-m4-preempt.iso

(The manual command requires an appropriate display/log device to view output.)

## Negative and independent evidence

- Three repeated real BIOS QEMU boots with exact native output and success 33.
- Changed source HTML -> rebuilt ISO -> exact altered kernel output.
- Without CPUID x2APIC support, fail-stop marker with non-success QEMU exit 51.
- Intentionally misaligned saved interrupt-stack pointer rejected before use.
- Masked local timer: no software yield, B cannot progress; bounded host timeout.
- Invalid probe combinations rejected by builder, no invalid image.
- Independent GCC -O0/-O3 UBSan checks of every C/assembly GPR/iret layout
  offset; old M1/M3/M4 tests remain part of CI.

## Important limits and future stages

The LVT count 1000000 with divide-by-16 is an **emulator-specific proof
parameter**, not a calibrated 100Hz timer. No claims about accuracy,
throughput, fairness under arbitrary user workloads or multiple CPUs.
Saved state is only GPR/RFLAGS/CS/RIP/RSP/SS for the trusted ring-0 task
profile. **No FPU/SIMD, FS/GS base, CR3 address-space switch, nested IRQ,
syscalls, user stacks, ring-3 isolation, SMP, UEFI or physical PC support.**
Tasks and stacks are static, do not terminate via ordinary process cleanup
and are not an interface exposed to HTML code.

The demo modifies privileged x2APIC MSRs only in the guest (QEMU), opted in.
No firmware, disk partition or host kernel modifications. The existing M4-B1
legacy PIC IRQ path remains independent and intentionally requires no-APIC.

Next: **M4-C** trusted ring3 entry/return and minimal syscall under guarded
private mappings; then **M4-D** forbidden user access proof and isolated
fault/cleanup policy. M4 milestone is **NOT COMPLETE** before these gates.
