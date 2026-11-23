# M3 — x86-64 TSS, dedicated IST fault stacks and real #DF delivery

**Scope:** a kernel-only, single-CPU **opt-in** TSS/IST exception-stack proof. This does not enable external interrupts, keyboard input, scheduling, user privilege transitions, or SMP. The normal HTML kernel and browser Boot Lab are unaffected.

## Real native implementation

With `--exception-idt --tss-ist`, `boot/tss_ist.c` defines a valid 104-byte AMD64 TSS and a canonical 16-byte available 64-bit TSS descriptor; builds a small private five-entry GDT (null, ring0 64-bit code, ring0 data, two TSS entries); executes `cli; lgdt; lretq` to reload CS; reloads DS/ES/SS; and executes privileged `ltr` for selector 0x18. The **active Limine CR3 and original kernel stack are not replaced**; all new GDT/TSS storage resides inside the kernel. The TSS sets IST1 to the top of a dedicated aligned 16KiB double-fault emergency stack, IST2 to a different 16KiB page-fault exception stack. `boot/exception_idt.c` sets IDT vector 8 IST=1 and vector 14 IST=2; all other vectors remain in the established fail-stop IDT.

The existing restricted one-shot #PF recovery runs on IST2, maps an owned zero-initialized frame, then returns through `iretq` to retry the interrupted CPU load. This works in the same QEMU image as the physical memory pool, private CR3 alias, TSS, IDT and framebuffer.

A **test-only** `--double-fault-test --test-exit` image first poisons its IST2 pointer, then triggers a **genuine CPU #PF**. The CPU fails while trying to deliver that exception on the invalid IST2 stack and raises actual vector 8 (#DF), which switches to the independent valid IST1 stack. The error path logs `M3_IST_DF_STACK_OK`, `M3_EXCEPTION V=08`, saved RIP and error code, then exits QEMU with non-success status 45. There is no fake diagnostic invocation or artificial call to the #DF handler. It **never tries to recover a double fault**.

## Reproduce

```sh
python3 -m unittest tests.test_tss_ist -v
python3 scripts/test_tss_ist.py
python3 scripts/build_boot.py --exception-idt --tss-ist --out build/html-kernel-m3-ist.iso
```

Unit test compiles the native C11 descriptor builder with GCC `-O0` and `-O3` and UndefinedBehaviorSanitizer; checks exact 104-byte TSS layout, 16-byte descriptor, canonical base, limit range and rejection without corrupting the output. Actual BIOS QEMU tests boot original and source-mutated HTML kernels; force a normal #PF on IST2 and an actual #DF on IST1; demonstrate the one-shot #PF recovery's `iretq` and native framebuffer composition; and reject unsafe CLI combinations (`--double-fault-test` requires `--test-exit` and an explicitly installed TSS/IDT).

**Observed independently on the mini PC** on 2026-11-23: normal changed-source boot, #PF `M3_IST_PF_STACK_OK`, actual #DF `M3_IST_DF_STACK_OK` with vector 08, recovery on IST2, full memory/IDT/framebuffer composition and GCC host tests passed. Each CI run must be tied to its exact commit; the docs alone are not CI evidence.

## Explicit limitations / not yet verified

- No hardware PIC/APIC IRQ delivery or acknowledgement, timer/keyboard handlers, preemptive tasks, SMP, per-CPU TSS, guard pages, ring3 I/O restrictions in practice, separate user/kernel memory spaces or arbitrary page fault recovery.
- A static single CPU GDT/TSS is **not** a full task switch or general kernel exception architecture.
- No UEFI boot, physical PC boot, other chipsets, or browser test for the new IST opt-in kernel.
- A recoverable #PF is strictly the preapproved **single demo alias**. All other faults (including #DF) fail-stop.

See [M3 exception IDT](M3_EXCEPTION_IDT.md), [M3 page fault recovery](M3_FAULT_RECOVERY.md) and [M3 private address translation](M3_PRIVATE_PAGING.md).
