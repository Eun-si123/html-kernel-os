/* M3: isolated test page tables, without editing Limine's active CR3 tree.
 * This is NOT a general-purpose virtual memory allocator.
 */
#include "paging_probe.h"
#include "page_pool.h"
#include "limine.h"
#include <stdint.h>

#ifdef HTMLK_M3_PAGING_UNMAP_FAULT_TEST
#ifndef HTMLK_M3_EXCEPTION_IDT
#error "unmapped-alias fault test requires an installed exception IDT"
#endif
#endif

static void report(const char *message) {
    while (*message) {
        uint8_t b = (uint8_t)*message++;
        __asm__ volatile ("outb %0, %1" : :
                          "a"(b), "Nd"((unsigned short)0xe9));
    }
}

__attribute__((noreturn))
static void failed(const char *marker) {
    report(marker);
#ifdef HTMLK_QEMU_TEST_EXIT
    /* Fail = (0x17 << 1) | 1 = 47, never the test PASS status 33. */
    __asm__ volatile ("outb %0, %1" : :
                      "a"((uint8_t)0x17), "Nd"((unsigned short)0xf4));
#endif
    __asm__ volatile ("cli" ::: "memory");
    for (;;) __asm__ volatile ("hlt" ::: "memory");
}

void htmlk_paging_probe(const struct limine_memmap_response *map,
                        const struct limine_hhdm_response *hhdm) {
    if (map == 0 || hhdm == 0 || map->entries == 0 ||
        map->entry_count == 0 || map->entry_count > HTMLK_MAX_MEMORY_REGIONS) {
        failed("M3_PAGING_NO_MAP\n");
    }
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4, %0" : "=r"(cr4));
    if ((cr4 & (UINT64_C(1) << 12)) != 0) {
        failed("M3_PAGING_LA57_UNSUPPORTED\n");
    }
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i = 0; i < map->entry_count; ++i) {
        if (map->entries[i] == 0) failed("M3_PAGING_NULL_REGION\n");
        regions[i].base = map->entries[i]->base;
        regions[i].length = map->entries[i]->length;
        regions[i].type = map->entries[i]->type;
    }
    struct htmlk_page_pool pool = {0};
    if (!htmlk_page_pool_init(regions, map->entry_count, &pool)) {
        failed("M3_PAGING_NO_USABLE_POOL\n");
    }

    uint64_t old_cr3;
    __asm__ volatile ("mov %%cr3, %0" : "=r"(old_cr3));
    const uint64_t old_root_phys = old_cr3 & HTMLK_PAGING_PHYS_MASK;
    if (old_root_phys == 0 || hhdm->offset == 0 ||
        (hhdm->offset & (HTMLK_PAGE_SIZE - 1)) != 0 ||
        hhdm->offset > UINT64_MAX - old_root_phys) {
        failed("M3_PAGING_BAD_HHDM_OR_CR3\n");
    }
    uint64_t frames[5];
    for (unsigned i = 0; i < 5; ++i) {
        if (!htmlk_page_take(&pool, &frames[i]) ||
            frames[i] == 0 ||
            frames[i] > HTMLK_PAGING_PHYS_MASK ||
            hhdm->offset > UINT64_MAX - frames[i] - HTMLK_PAGE_SIZE) {
            failed("M3_PAGING_FRAME_EXHAUSTED\n");
        }
    }
    const uint64_t offset = hhdm->offset;
    volatile uint64_t *old_root =
        (volatile uint64_t *)(uintptr_t)(offset + old_root_phys);
    volatile uint64_t *root =
        (volatile uint64_t *)(uintptr_t)(offset + frames[0]);
    volatile uint64_t *pdpt =
        (volatile uint64_t *)(uintptr_t)(offset + frames[1]);
    volatile uint64_t *pd =
        (volatile uint64_t *)(uintptr_t)(offset + frames[2]);
    volatile uint64_t *pt =
        (volatile uint64_t *)(uintptr_t)(offset + frames[3]);
    volatile uint64_t *physical_alias =
        (volatile uint64_t *)(uintptr_t)(offset + frames[4]);

    /* Only the private newly allocated root is modified. */
    for (unsigned i = 0; i < 512; ++i) root[i] = old_root[i];
    if (!htmlk_paging_wire(root, pdpt, pd, pt,
                           frames[1], frames[2], frames[3], frames[4])) {
        failed("M3_PAGING_RESERVED_SLOT_OCCUPIED\n");
    }
    *physical_alias = UINT64_C(0x4d3356414c494153); /* "M3VALIAS" */
    __asm__ volatile ("mov %0, %%cr3" : : "r"(frames[0]) : "memory");
    report("M3_PAGING_MAP_OK\n");

    volatile uint64_t *virtual_alias =
        (volatile uint64_t *)(uintptr_t)HTMLK_PAGING_VADDR;
    if (*virtual_alias != UINT64_C(0x4d3356414c494153)) {
        failed("M3_PAGING_ALIAS_WRONG\n");
    }
    *virtual_alias = UINT64_C(0x4d33504147454d41); /* different value */
    if (*physical_alias != UINT64_C(0x4d33504147454d41)) {
        failed("M3_PAGING_HHDM_ALIAS_WRONG\n");
    }
    report("M3_PAGING_ALIAS_OK\n");

    /* Revoke the private 4KiB virtual alias and invalidate its TLB entry. */
    pt[0] = 0;
    __asm__ volatile ("invlpg (%0)" : : "r"(virtual_alias) : "memory");
    if (pt[0] != 0) failed("M3_PAGING_UNMAP_FAILED\n");
    report("M3_PAGING_UNMAPPED\n");

#ifdef HTMLK_M3_PAGING_UNMAP_FAULT_TEST
    /* CPU raises a real #PF (P=0); the previously installed IDT
     * reports CR2=0xffffa00000000000 and exits QEMU non-success 45. */
    volatile uint64_t must_fault = *virtual_alias;
    (void)must_fault;
    failed("M3_PAGING_BAD_UNMAP_ALLOWED\n");
#else
    __asm__ volatile ("mov %0, %%cr3" : : "r"(old_cr3) : "memory");
    report("M3_PAGING_RESTORED\n");
#endif
}
