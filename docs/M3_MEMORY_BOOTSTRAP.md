# M3 — first physical-memory bootstrap (opt-in, partial)

**Status:** an auditable experimental M3 *bootstrap slice*, not the M3 completion gate or a production allocator. The first implementation was actually executed under headless QEMU BIOS in GitHub CI run `45092535635` using the pinned Limine 12.11.1 boot protocol. The integrated M2+M3 PR run `45093041196` completed SUCCESS at `51e91ad`; it includes all previous M2 CI steps. UEFI, physical hardware, virtual-memory page-table management, faults/interrupt handlers, concurrent tasks and real application memory isolation remain **NOT VERIFIED / NOT IMPLEMENTED**.

## What is executable

- `boot/kernel_entry.c` only makes Limine **memory-map** and **higher-half direct-map (HHDM)** requests when built with `--memory-probe`. The ordinary kernel boot path and its source-generated output are unchanged.
- `boot/page_pool.c/.h` is an independent freestanding C11 allocator contract. A map must contain **1..128** entries, each with nonzero length, no end overflow and no overlap (even with reserved regions). Only Limine type `USABLE=0` is considered; page zero is never returned.
- From a validated usable range, the pool selects exactly **16 aligned 4KiB pages**. Metadata lives outside those pages. `htmlk_page_take` allocates each page once, then returns false without changing the output argument on the 17th request. No free operation, ownership handoff or concurrent access is implemented.
- `boot/memory_probe.c` gets the real Limine response and HHDM offset. It validates both, allocates 16 pages and writes/reads an 8-byte sentinel through each HHDM-mapped physical page. These are real QEMU memory operations, **not fake strings**. On failure it prints a reason to QEMU debugcon and halts (or exits QEMU with non-success code **39** in the CI test image).
- A test-only `--memory-probe-badmap` flag corrupts **only a local copy** of a valid boot map. The kernel must reject it with `M3_BADMAP_REJECTED` and QEMU exit 39. This never modifies actual Limine metadata.

## Expected QEMU evidence

The opt-in test image emits these debugcon markers *before* handing off to the regular source-generated `kernel_main()`:

```text
M3_MEMMAP_VALIDATED
M3_PAGES_WRITTEN
M3_EXHAUSTION_HANDLED
Hello from HTML Kernel!
Native code, not a browser.
```

The wrong-map image emits only `M3_BADMAP_REJECTED`, then signals failure, **never success**. The separate source-mutation control changes the last two lines, proving the generated HTML kernel still actually runs after memory bootstrap.

## How to reproduce

Requirements: x86-64 Linux, Python 3.12, GCC, QEMU, xorriso and network access for checksum-verified pinned Limine binaries, or an existing verified cache.

```sh
python3 scripts/test_m3_memory.py
python3 scripts/build_boot.py --memory-probe --out build/html-kernel-m3-memory.iso
```

The test script also compiles and executes `tests/native/test_page_pool.c` against the same allocator with `-O0` and `-O3`, using GCC UndefinedBehaviorSanitizer. Positive cases cover sequential pages, alignment and page-zero exclusion; negative cases cover reserved-only, too-short, zero-length, overflow, overlaps, empty or oversized maps, invalid pointers and pool exhaustion. The QEMU path checks actual memory write/read, source mutation and malformed-map failure independently.

**Important safety boundary:** this pool's 16 pages are boot-time probe-owned only; it does **not** expose physical-memory pointers to HTML user programs. Neither virtual address mapping nor page-table ownership has been designed/tested. Future M3 work must reserve all kernel/bootloader regions, establish page-table ownership, handle page faults, invalid mappings and concurrent or repeated allocations with clean failure paths, and expand beyond the 16-page demonstration only with new tests. Do not use this ISO as proof of real PC compatibility.
