# M3 — Bounded physical-frame ownership and recoverable CPU page fault

**Scope:** a narrow but genuine native x86-64 **fault recovery** proof, NOT general on-demand paging or user-process memory safety. This work builds on the verified M3 Limine USABLE memory map, the 16-page physical pool, the private 4KiB PML4 alias and the CPU IDT from PRs #38–#41.

## Implemented and directly tested

- `boot/frame_owner.c/.h` adds a pure freestanding C11 **16-frame owner registry**, with explicit TABLE and DATA tags, bounded lowest-free allocation, deterministic release/reuse, no double-free, wrong-owner refusal, no page zero and fail-closed initialization. It only tracks ownership; physical bytes are accessed separately through a trusted Limine HHDM.
- The existing private CR3 paging probe now gets its four table pages and its original mapped DATA page through this registry rather than an untracked one-way pointer. It **never edits the original Limine page tables**. After unmapping the alias and restoring the original CR3, it releases all of its owned frames; an optional `--owned-frame-test` then reclaims all 16 and verifies exhaustion, wrong-owner release and double-free refusal in the **actual QEMU guest**.
- With explicit `--paging-recover-test --exception-idt --paging-probe`, the private alias is deliberately unmapped, an actual CPU read causes **#PF**, and IDT vector 14 calls a strictly restricted recovery handler. Recovery is permitted once, only for a not-present kernel read at the exact demo alias `0xFFFFA00000000000` and only while the approved private CR3 is active. The handler allocates another owned DATA frame, clears the full 4KiB via HHDM, installs a supervisor-only RW PTE and invalidates its TLB entry before returning.
- A real hardware `iretq` retries the **original faulting memory load**. The resumed code observes the freshly zero-filled page, then writes through the virtual alias and independently verifies the corresponding physical HHDM value. The alias is revoked again, the original CR3 restored, all owned frames released, and source-generated HTML code runs.
- CPU page-table **Accessed/Dirty** bits may be set by hardware during instruction retry. The test checks the frame address and required permission flags, not a falsely exact PTE byte pattern. Compiler/ISR shared recovery metadata uses `volatile` and a memory compiler barrier.
- All unrelated/unarmed/second faults still fail-stop with the existing M3 IDT. No arbitrarily faulting address, user program or code from HTML source may trigger allocation.

## Reproduce

```sh
python3 -m unittest tests.test_frame_owner -v
python3 scripts/test_paging_recovery.py
python3 scripts/test_paging_probe.py
```

Tests include GCC -O0/-O3 UBSan pure C contracts (all 16 frames; strict owner, reuse, exhaustion and double free), actual BIOS QEMU native HTML boot + changed HTML source, actual one-shot page-fault handling and resumed CPU load, an **unarmed wrong-address fault which must fail-stop** with QEMU exit 45 and CR2, four-feature integration with physical pool + private CR3 + IDT + video output, and invalid CLI flag combinations. The proof requires real QEMU output: a hand-written log is not sufficient. The public browser site is not changed by this branch.

## Remaining limitations (M3 NOT fully complete)

This fixed arena is **not a reusable production virtual-memory manager**. There is no cross-process memory ownership, arbitrary map/unmap API, kernel heap/stack management, page-table lifetime reclamation across workloads, TSS/IST recovery for broken stacks/double faults, system interrupts, SMP TLB shootdown, NX/W^X policy, or safe user-space page fault recovery. Only the specific one-shot test address and current CR3 are allowed. No UEFI, physical PC or browser validation for this M3 feature. Future M3 acceptance work must isolate faults onto dedicated exception stacks, define a general bounded virtual memory manager/ownership policy, and verify multi-page map/fault/unmap and rollbacks without weakening this negative control.

References: [M3 private paging](M3_PRIVATE_PAGING.md), [M3 fail-stop exception IDT](M3_EXCEPTION_IDT.md), [M3 physical pool](M3_MEMORY_BOOTSTRAP.md).
