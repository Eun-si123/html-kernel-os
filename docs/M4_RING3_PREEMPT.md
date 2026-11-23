# M4-D1/D2 — Real CPL3 preemption and surviving user fault (QEMU-only)

**Status:** opt-in single-vCPU BIOS QEMU experiment. Default HTML kernel remains unchanged.

## D1: actual CPU timer preempts never-yielding Ring 3 code

Build:

    python3 scripts/build_boot.py --exception-idt --tss-ist --user-preempt-probe --test-exit --out build/m4-d1.iso

Use QEMU q35, qemu64,+x2apic, one CPU, 256 MB, port E9 debugcon
and ISA debug-exit port F4. See scripts/test_m4_user_preempt.py.

Real periodic x2APIC IRQ on IDT vector 0x40 interrupts two independent
CPL3 loops. Neither task invokes a syscall, yield, sleep or HLT.
A and B have different physical six-frame sets (PML4, PDPT, PD, PT,
read-only user code and RW user stack), though they use the same
virtual entry and stack addresses. Their privileged interrupt
stacks are separate 16 KiB arrays with independent canaries.

The timer IRQ begins on the selected task's TSS.RSP0 kernel stack,
saves 15 GPRs and all five CPL3 IRET fields, and verifies CS/SS,
RIP/RSP, IF, current CR3, RSP0, stack bounds, RBX/R12 sentinels
and private physical stack counter progress. It updates TSS.RSP0,
reloads CR3, EOIs the APIC, then uses hardware IRETQ to return
to the other task. A spurious vector 0xff IRETs without EOI.

Expected QEMU output excerpt:

    M4_D1_USER_A_0
    M4_D1_USER_B_0
    M4_D1_USER_A_1
    M4_D1_USER_B_1
    M4_D1_USER_A_2
    M4_D1_USER_B_2
    M4_D1_CPL3_PREEMPT_PASS
    M4_D1_ALL_FRAMES_RECLAIMED

## D2: real fault of preempted A, continuation of running B

Build with additional --user-preempt-fault, or use
scripts/test_m4_user_fault_preempt.py.

Once both tasks have made at least two observed IRQ-driven progress
steps, the trusted scheduler arms a private flag for A. A executes
a genuine CPL3 read of supervisor virtual address FFFFFFFF80001000.
The CPU delivers #PF with user error 0x5 and exact CR2, on IST2.

Only this exact A failure may be recovered: check the active task,
physical CR3, RIP, CPL3 selectors, RSP, error/CR2, IST2 and previous
progress. Unknown #PF/#GP events remain fail-stop. From IST2 the
handler abandons the poisoned A context, selects the *existing*
saved B IRQ frame, updates TSS.RSP0/CR3, reclaims six A frames,
then performs direct assembly IRET to the surviving B program.
B continues for three additional timer observations; after it
finishes, the kernel restores the original Limine CR3 and main
kernel stack, and reclaims all B frames with owner checks.

Native QEMU log excerpt:

    M4_D1_USER_A_1
    M4_D1_USER_B_1
    M3_IST_PF_STACK_OK
    M4_D2_A_PF_ERROR_5
    M4_D2_A_RECLAIMED
    M4_D1_USER_B_2
    M4_D1_USER_B_3
    M4_D1_USER_B_4
    M4_D2_CPL3_FAULT_SURVIVOR_PASS
    M4_D1_ALL_FRAMES_RECLAIMED

Success is native QEMU debug-exit 33, followed by exact output
from the compiler-generated HTML kernel body.

## Independent controls

- Three real QEMU boots each for D1 and D2, exact trace assertions.
- Changed HTML source produces a different ISO and changed guest output.
- Without x2APIC the CPU is rejected (exit 57), not simulated.
- A masked timer makes the non-yielding user task spin indefinitely,
  so a bounded host timeout with no scheduler progress is required.
- Forged CPL0 code selector for the next IRQ context is rejected
  before return to CPL3 (exit 57).
- Deliberate unexpected survivor B #GP raises genuine vector 13 and
  fails with exit 45, never reusing A's fault cleanup handler.
- Invalid probe combinations cannot produce an ISO.
- Native pure-C 160-byte IRQ frame validator: GCC UBSan -O0/-O3;
  rejects selectors, IF, stack bounds, invalid RIP and RBX/R12.
- Legacy M1/M3/M4-A/B1/B2/C1/C2 tests remain independent.

## Scope and security limits

This is a **bounded single-vCPU interrupt + memory-isolation proof**,
not a general-purpose untrusted-process kernel. Fixed trusted user
payloads; no ELF loader, generalized syscalls/copyin or IPC. No
real PC, SMP, UEFI, calibrated timer, nested IRQ/FPU/FS/GS save-restore,
SMEP/SMAP policy or broad memory ownership APIs. The scheduler rejects
LA57 and PCID; no hardware compatibility beyond explicit QEMU
configuration is implied. M5 and M6 are not implemented. Further M4
hardening and user ABI remain tracked in Issue #61.
