# M4-C1 — genuine Ring 3 and int 0x80 (bounded QEMU)

**Status: local real QEMU + host-native UBSan PASS; check exact PR-head CI
before merging. NOT the M4 completion gate.**

## Scope

An opt-in, isolated probe demonstrates a real x86-64 CPU privilege boundary
inside the HTML-derived Limine kernel, not Linux compatibility or a process
loader. It reuses the verified M3 Limine HHDM/memory-map, 16 owned 4KiB frames,
IDT and TSS/IST as its foundations. A private PML4 is copied from the
active bootloader root; inherited kernel entries explicitly have U/S cleared.
Only one unused PML4 slot 128 is wired for user-mode memory:

- One 4KiB user **code page** with present + user, but **not writable**.
- One 4KiB user **stack page** with present + user + writable.
- All PML4/PDPT/PD ancestor entries on the user path include user permission.
- Six owned frames: private root, PDPT, PD, PT, executable code, writable stack.
  Original Limine root and bootloader mappings are never modified.
- Executable user bytes are copied from one fixed, trusted assembly text range
  (not read from arbitrary HTML source, filesystem or untrusted executables).

The dedicated opt-in GDT extends the existing M3 selectors with 0x2B (user CS)
and 0x33 (user SS). TSS.RSP0 points to a dedicated 16KiB CPL0 syscall stack;
#DF IST1 and #PF IST2 remain distinct. A DPL3 IDT vector 0x80 allows real
user-mode INT 0x80. The CPU switches onto RSP0; the assembly entry preserves
all 15 GPRs, and the kernel validates saved CS/SS/RIP/RSP and syscall ID.
Syscall 0 receives exact integer 0x1234, logs its success, and iretq resumes
CPL3. The user test also proves a real stack store/readback. Syscall 1
performs an explicit controlled exit, restoring the original kernel CR3 and
main stack. The kernel releases all six owned frames and then executes the
original HTML-generated kernel code.

## Reproduce

    python3 scripts/test_m4_user.py
    python3 scripts/build_boot.py --exception-idt --tss-ist --user-probe --out build/html-kernel-m4-user.iso

Real QEMU BIOS default q35 CPU profile, -m 256M. Normal test uses
--test-exit and expects QEMU exit 33 and exact marker sequence:

    M3_TSS_IST_READY
    M3_IDT_READY
    M4_USER_PAGE_TABLES_READY
    M4_RING3_CPL3_SYSCALL_OK
    M4_RING3_EXIT_OK
    M4_RING3_MAIN_RESTORED
    Hello from HTML Kernel!
    Native code, not a browser.

## Real-CPU negative controls

- --user-bad-syscall: valid CPL3 first call, then unsupported #99 is rejected
  by ring0 validation (QEMU exit 53, no HTML kernel continuation).
- --user-privileged-io: CPL3 OUTB must raise **#GP vector 13**, error 0,
  non-success QEMU exit 45.
- --user-read-kernel: CPL3 reads kernel supervisor-only RIP address
  0xFFFFFFFF80001000; genuine **#PF vector 14**, error bits 0x5 (present +
  user read) and precise CR2, QEMU exit 45. #PF IST2 stack must be observed.
- --user-write-code: CPL3 writes to its own read-only code at
  0x0000400000000000; real **#PF vector 14**, error 0x7 (present + write +
  user) and exact CR2, QEMU exit 45. #PF IST2 must be observed.
- Original/altered HTML source builds different ISO, changes kernel output,
  and rejects stale source output in QEMU.
- Invalid/mixed builder options must fail before generating an image.
- GCC UBSan -O0/-O3 host tests reject duplicate, zero, misaligned and
  out-of-range physical-frame inputs and verify user-path ancestor flags,
  read-only code and read/write stack. The *separate* native guest owner
  registry rejects wrong-owner releases.

## Not yet implemented

This is a **single trusted, static user task** with an intentional syscall
exit. Faults are fail-stop: a bad CPL3 task does **not** get isolated cleanup
with a surviving second task. No production syscall ABI, pointer copy-in/out,
user dynamic loader, executable signing, enforced NX on stack, task switching,
FPU/FS/GS state, SMAP/SMEP, SMP, disk drivers, UEFI or physical-PC evidence.
No arbitrary HTML source can yet create a ring3 process. The opt-in user
probe cannot be combined with other task/memory/IRQ experiments.

Next M4-C2/D acceptance: two *separate* user tasks/processes, per-task CR3,
proper fault-time termination + frame reclamation without kernel corruption,
surviving task progress after another task faults, and independently tested
privileged memory/system call policies. M4 remains **OPEN** until then.
