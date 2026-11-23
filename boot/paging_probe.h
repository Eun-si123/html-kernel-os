/* M3 opt-in private page-table experiment; no general kernel VM allocator. */
#ifndef HTMLK_PAGING_PROBE_H
#define HTMLK_PAGING_PROBE_H

#include <stdbool.h>
#include <stdint.h>

#define HTMLK_PAGING_SLOT 320U
#define HTMLK_PAGING_VADDR UINT64_C(0xffffa00000000000)
#define HTMLK_PAGING_ENTRY_RW UINT64_C(3)
#define HTMLK_PAGING_PHYS_MASK UINT64_C(0x000ffffffffff000)

/* Pure C11 page-table builder: root is a private copy of active PML4.
 * Never writes any entry if arguments/slot are invalid. The caller owns
 * all four distinct 4KiB aligned physical frames + mapped pointers. */
bool htmlk_paging_wire(volatile uint64_t *root,
                       volatile uint64_t *pdpt,
                       volatile uint64_t *pd,
                       volatile uint64_t *pt,
                       uint64_t pdpt_phys, uint64_t pd_phys,
                       uint64_t pt_phys, uint64_t page_phys);

/* Restricted 4KiB leaf map/unmap inside a caller-owned private page table.
 * Never overwrites occupied entries or maps duplicate physical frames.
 * Unmap requires the expected physical owner; callers must then invalidate
 * the virtual address TLB entry BEFORE returning its physical page to pool.
 */
bool htmlk_paging_leaf_map(volatile uint64_t *pt,
                           unsigned index, uint64_t phys);
bool htmlk_paging_leaf_unmap(volatile uint64_t *pt,
                             unsigned index, uint64_t expected_phys);

struct limine_memmap_response;
struct limine_hhdm_response;

/* BIOS-QEMU proof: copy bootloader CR3 to a private root, temporarily map
 * one supervisor-only test page, check HHDM alias, unmap, restore CR3.
 * A separate fault-injection build reads the unmapped virtual alias with
 * the already verified M3 IDT installed. No IRQ/SMP/user-mode support. */
#ifdef HTMLK_M3_PAGING_RECOVER_TEST
/* Invoked by x86-64 #PF ISR only; returns true exclusively for one approved
 * non-present supervisor load while the private CR3 is active. */
bool htmlk_paging_recover_page_fault(uint64_t fault_address, uint64_t error_code);
#endif

void htmlk_paging_probe(const struct limine_memmap_response *map,
                        const struct limine_hhdm_response *hhdm);

#endif
