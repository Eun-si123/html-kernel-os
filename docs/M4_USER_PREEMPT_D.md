# M4-D — genuine x2APIC preemption of two independent Ring-3 address spaces

**Experimental opt-in QEMU BIOS, single vCPU, no physical PC or UEFI evidence.**
M4-B2 preempted only Ring-0 kernel tasks. M4-C2 isolated two Ring-3 user
processes and survived a real #PF, but entered them sequentially with IF=0.
M4-D connects these two **separate** real-CPU properties.

## Build, boot and source provenance

```sh
python3 scripts/build_boot.py --out build/html-kernel-m4-user-preempt.iso \
  --exception-idt --tss-ist --user-preempt-probe
HTMLK_CACHE_DIR=build/.cache python3 scripts/test_m4_user_preempt.py
python3 -m unittest tests.test_user_timer_policy -v
```

The native QEMU proof runs `-M q35 -cpu qemu64,+x2apic -smp 1`,
using the pinned Limine boot image. `--test-exit` is a harness-only variant
whose guest debug-exit 0x10 makes QEMU return 33. A standalone non-test ISO
halts after executing source-generated HTML. Neither is a web simulation.

## Executed native mechanisms

- The real Limine memory map supplies exactly twelve owner-tagged physical
  4-KiB frames for two independently live user PML4/PDPT/PD/PT roots,
  read-only executable code and writable user stacks. The common user VA
  resolves to distinct backing frames in each task's CR3. Original Limine
  kernel mappings retain supervisor-only access.
- The private GDT/TSS has Ring-3 CS/SS; per-task 16-KiB supervisor kernel
  stacks are selected by TSS.RSP0 on *every* task switch. #PF on IST2 and
  #DF on IST1 retain their own emergency stacks.
- The actual x2APIC local timer (vector 0x40) interrupts each non-yielding
  CPL3 busy loop. Assembly saves 15 GPRs and the CPU-supplied five-word
  privilege-transition IRET frame. The dispatcher validates expected
  user selectors, user RIP/RSP, IF, stack range and stack canary before
  switching CR3 and TSS.RSP0, sending EOI and doing IRETQ. The boot-time
  frame initializes 15 distinct task-specific GPR sentinel values; **both
  user programs check every value after repeated real timer switches**.
  A deliberately corrupted sentinel must trigger real CPL3 #UD, not success.
- After A0/B0/A1/B1/A2/B2 timer progress, the kernel arms a **per-process**
  user stack flag. Offender A then actually reads supervisor kernel VA
  `FFFFFFFF80001000`, provoking CPU #PF error **0x5** on IST2. A's
  CR3/CS/SS/RIP/RSP/CR2/error are independently checked. The kernel
  switches to the original supervisor CR3, reclaims **only** A's six pages,
  resumes B from its *saved* interrupt frame, and B issues legitimate
  INT 0x80 syscall/exit. All B frames are reclaimed and HTML output follows.

## Automated negative controls and limits

`scripts/test_m4_user_preempt.py` requires three full **real QEMU**
boots with exact ordered IRQ progress, a changed HTML source producing a
different bootable ISO and output, and separate x2APIC-unsupported CPU
failures. Timer masking must timeout on the original non-yielding CPL3 loop.
Forged CPL0 selector, unknown B syscall and incompatible builder flag
combinations must fail closed. An unexpected real B #GP after A's retirement
must **panic** rather than steal A's allowed fault recovery path.
A negative injects the wrong active CR3 during an IRQ and requires an
immediate non-success owner-context exit. A second test revokes B's
code PTE **after B first executed**, switches CR3 and requires real CPU
#PF with B's instruction virtual address; no stale user instruction
translation may keep that task running. A duplicate A frame release is
explicitly required to fail while B's six owned pages stay live.
`tests/test_user_timer_policy.py` independently builds the pure validator
at GCC `-O0` and `-O3` with UBSan and rejects wrong privilege, flags,
RIP, RSP, frame boundaries and malicious kernel selectors.

**Not a general-purpose user process subsystem:** the two user payloads are
fixed trusted test code copied into private mapped pages; no arbitrary
binary loader, process creation from HTML, per-process heap, IPC, dynamic
user pointers, FPU/SIMD or FS/GS context preservation, SMP, APIC timer
calibration, general interrupt routing, production crash recovery, UEFI
runtime verification, physical PC, or supported devices. In particular,
this probe is **opt-in** and does not turn the ordinary HTML kernel into a
time-sharing general-purpose OS. Any unapproved user fault fails closed.
