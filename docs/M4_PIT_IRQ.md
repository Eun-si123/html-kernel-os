# M4 Phase B1 — real legacy PIT/PIC IRQ0 (bounded QEMU)

**Experimental timer integration, not completion of Phase B or M4.**

A separate opt-in ISO routes legacy 8254 PIT IRQ0 through a remapped 8259 PIC
to IDT vector 0x20. Its x86-64 interrupt entry acknowledges each IRQ and
increments a volatile CPU tick count. Each cooperative ring-0 task executes
an atomic STI/HLT/CLI wait before its next explicit yield; a strictly increasing
IRQ count is necessary for both tasks to complete. The handler does **not**
perform a context switch. Six real IRQ-driven task progress events plus the
original changed-source HTML kernel run in real QEMU.

Supported native test profile: QEMU q35 **-cpu qemu64,-apic**.
The legacy PIC LINT0 delivery path is not assured with a local APIC available.
When CPUID reports local APIC, the probe explicitly stops with marker
M4_TIMER_APIC_UNSUPPORTED and QEMU non-success exit 49. This avoids a frozen
guest on default qemu64/q35. No APIC, I/O APIC, HPET, SMP or physical PC
support is claimed for the timer probe. This restriction is **not** applied
to normal HTML boot images or the M4-A cooperative task test.

Commands:

    python3 scripts/test_m4_timer.py
    python3 scripts/build_boot.py --exception-idt --task-probe --timer-probe --out build/m4-irq.iso

The test asserts:
- GCC UBSan -O0/-O3 PIT divisor rate boundary validation.
- Real QEMU q35 no-APIC BIOS complete native task sequence and HTML output.
- HTML source-mutation oracle creates distinct ISO with exact changed output.
- Default APIC profile cleanly rejects with exit 49 and explicit marker.
- An IRQ0-masked QEMU negative control fails to make progress (bounded 4s).
- Invalid probe flags fail before building.

Status after B1: M4-A cooperative task contexts verified, M4-B1 legacy timer
interrupt delivery and opt-in tick-based cooperative pacing verified. Still
**NO preemption, timeslice save of interrupt context, ring-3 userspace,
syscalls, protected per-task address spaces or hardware generality**.
Next B2: APIC/IOAPIC route and genuine timer-driven preemption with a
safe IRQ context + FPU/FS/GS plan. Then M4-C ring3 and M4-D memory isolation.
