# M3 — Bounded 4KiB multi-page mapping and reclaimed physical frames

**Scope:** a deliberately bounded, freestanding **kernel-only** four-level x86-64 page-table mapping contract, not a production virtual memory manager. This extension builds on the already merged Limine memory map, 16 owned pages, independent CR3, IDT exception and TSS/IST stacks. It never edits the bootloader's original page tables.

## What actually runs

- Two pure C11 helpers in `boot/paging_tables.c`: `htmlk_paging_leaf_map` and `htmlk_paging_leaf_unmap`. They accept only a caller-owned private 512-entry **leaf** PT; refuse out-of-range indices, null pointers, physical address zero, unaligned or too-wide frames, occupied entries, duplicate physical-frame mappings, and unmap attempts against the wrong physical owner. They do not authorize user/ring3 access.
- With `--paging-probe --multi-page-test`, the actual x86-64 kernel first creates the existing private PML4 root and baseline alias `0xFFFFA00000000000`. In that active private CR3 it claims three additional DATA-owned 4KiB frames, maps leaf entries 1, 2 and 3, reads and writes each virtual alias **through the CPU**, compares against the independent HHDM physical view, and checks that duplicate/mismatched operations are rejected.
- It clears each leaf and executes `invlpg` **before** releasing the corresponding frame. This map/read/write/unmap/release sequence repeats **three complete rounds**. Every claimed frame must have exactly the same physical address on subsequent rounds and the original first-page mapping must remain intact. This is actual guest CPU memory behavior, not a C-only data structure.
- With opt-in `--multi-page-fault-test --exception-idt --test-exit`, an actual CPU read at the **revoked second page** `0xFFFFA00000002000` must raise vector14 #PF, with matching CR2 and error code 0; the kernel must terminate with QEMU non-success exit 45, never proceed to HTML-derived code.
- Combined mode also runs dedicated TSS/IST2 page fault recovery on the original first page, the 16-frame ownership exhaustion/double-free checks, Limine memory pool readback and live framebuffer pixels, then restores original CR3 and executes unchanged (and source-mutated) HTML kernel code.

## Reproducibility gates

```sh
python3 -m unittest tests.test_paging_tables -v
python3 scripts/test_multimap.py
python3 scripts/test_paging_probe.py
python3 scripts/test_paging_recovery.py
python3 scripts/test_tss_ist.py
```

Host C11 oracle: exact 4-level structure, permission flags, occupied/alias detection, zero/unaligned/out-of-range physical frames, unmap wrong-owner denial, idempotent negative controls and hardware Accessed/Dirty bit tolerance; compiled and executed with GCC `-O0` and `-O3` UBSan. Guest tests: source-original and source-modified BIOS QEMU images, true CPU physical aliasing for three pages over three rounds, actual revoked-page #PF, CLI failure controls, plus all M3 integration. Mini-PC independent actual QEMU and host GCC runs passed on 2026-11-23. The final GitHub Actions run and SHA must also pass before claiming a main-branch completion gate.

## What this does not imply

This is not a general-purpose kernel heap or VMM: no mapping outside the deliberately reserved PT, user/ring3 address spaces, arbitrary page-table creation and destruction, concurrent task ownership, SMP TLB shootdowns, NX/W^X policies, dynamic memory regions, physical machines or UEFI verification. The allocation arena is still **16 × 4KiB** and the tested kernel remains a single CPU, single image. The CPU fault recovery handler continues to support only **one preapproved supervisor address**, rejecting other faults. External hardware IRQ drivers, timers, keyboard input and scheduler belong to later scope. Avoid calling this a finished operating system.

See [M3 page-table bootstrap](M3_PRIVATE_PAGING.md), [M3 ownership and recovery](M3_FAULT_RECOVERY.md), [M3 exception stacks](M3_TSS_IST.md), and [M3 original memory map](M3_MEMORY_BOOTSTRAP.md).
