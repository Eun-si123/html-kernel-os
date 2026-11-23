# M3 — Private CR3 virtual page mapping proof

**Status:** experimental 4-level x86-64 page-table slice, not a general-purpose memory manager. **Verified in the merged main kernel (commit `6f407d0`, Actions `45097936323`) and on the experimental branch:** native GCC UBSan -O0/-O3 layout checks, genuine BIOS QEMU CR3 map/unmap alias, source-derived execution, post-unmap #PF (CR2), and combined physical pool/IDT/video test all PASSED in Actions run `45097571139`. This is not browser/UEFI/physical hardware evidence. No Pages, firmware, disk, UEFI or physical-hardware changes.

## Implemented operation

- With `--paging-probe`, the kernel asks pinned Limine for the memory map and higher-half direct map (HHDM). It verifies a reasonable 1–128-entry, non-overlapping map via the existing freestanding `page_pool`.
- It rejects 5-level mode (CR4.LA57) explicitly. The experiment supports **only 4-level paging**.
- It allocates five aligned 4KiB USABLE physical pages: one private PML4 root, one PDPT, one PD, one PT and one data page. The kernel reads the bootloader's active physical PML4 via HHDM and **copies its 512 entries** into the private root; the original Limine page tables are **never edited**.
- The pure `htmlk_paging_wire` helper refuses null/aliased pointers, unaligned, duplicate or unrepresentable physical frames, and any occupied PML4 slot 320. Otherwise it constructs a single supervisor-only, writable 4KiB mapping at pinned canonical virtual address `0xFFFFA00000000000`, using PML4[320], PDPT[0], PD[0], PT[0]. User-accessible flag stays clear. The unused private page tables are initialized to zero.
- `mov cr3` activates the private root, an actual CPU read/write of the new virtual alias is cross-checked against the original HHDM physical address, and `M3_PAGING_ALIAS_OK` is emitted only if both match. The kernel sets the leaf PTE to zero, issues `invlpg`, restores the exact saved CR3 and then runs **the original source-generated HTML kernel**.
- A separate `--paging-fault-test` image (which requires `--paging-probe --exception-idt`) tries reading the alias **after unmap while still running under the private CR3**. A genuine `#PF` must enter the verified M3 IDT, report vector 14, RIP, error code zero and `CR2=FFFFA00000000000`, then exit QEMU with **non-success code 45**. Faulting ISO must never reach `kernel_main`.
- Failures before mapping report a distinct `M3_PAGING_*` marker and QEMU non-success exit 47. No kernel page table is overwritten on failure. Physical pages are **probe-owned and not returned** to an operating memory manager; only the temporary virtual alias is revoked.

## Run and validate

```sh
python3 -m unittest tests.test_paging_tables -v
python3 scripts/test_paging_probe.py
python3 scripts/build_boot.py --exception-idt --paging-probe --out build/html-kernel-m3-paging.iso
```

Unit tests verify the exact four-level layout, bit flags, non-user privilege, fail-closed duplicate/unaligned/zero/out-of-range frames and preservation of existing root entries under GCC UBSan `-O0`/`-O3`. The BIOS QEMU test must validate both normal and source-modified ISO execution, a real post-unmap CPU #PF, invalid CLI invocation controls and composition with the earlier physical pool, exception IDT and native video console.

## Deliberately excluded

This is **not** safe general virtual memory allocation. It does not implement independently owned page-table lifetimes, arbitrary map/unmap APIs, a free list, TLB shootdowns, SMP, process address spaces, NX/W^X, user-level isolation, TSS/IST or page-fault recovery. The hard-coded unused PML4 slot 320 is only an audited demonstration; if an existing Limine mapping occupies it, the experiment **fails closed**, never overwrites it. Host HHDM and page-map validity are trusted Limine inputs. The status ledger distinguishes QEMU, browser, UEFI and physical-hardware evidence. The next production-grade step requires an allocator/ownership model, virtual-address reservation and safe page-table updates with resource-exhaustion and invalid-map controls, not reusing this demo as a general allocator.

References: [Intel SDM, volume 3 paging tables](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), [M3 physical pool](M3_MEMORY_BOOTSTRAP.md) and [M3 fail-stop IDT](M3_EXCEPTION_IDT.md).
