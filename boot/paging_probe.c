/* M3: isolated test page tables, without editing Limine's active CR3 tree.
 * This is NOT a general-purpose virtual memory allocator.
 */
#include "paging_probe.h"
#include "page_pool.h"
#include "frame_owner.h"
#include "limine.h"
#include <stdint.h>

#if defined(HTMLK_M3_PAGING_UNMAP_FAULT_TEST) || defined(HTMLK_M3_PAGING_RECOVER_TEST)
#ifndef HTMLK_M3_EXCEPTION_IDT
#error "paging fault injection or recovery requires an installed exception IDT"
#endif
#endif
#if defined(HTMLK_M3_PAGING_UNMAP_FAULT_TEST) && defined(HTMLK_M3_PAGING_RECOVER_TEST)
#error "recovery and fail-stop fault tests are mutually exclusive"
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

#ifdef HTMLK_M3_PAGING_RECOVER_TEST
static struct htmlk_frame_registry * volatile recovery_registry;
static volatile uint64_t * volatile recovery_table;
static volatile uint64_t recovery_cr3_phys, recovery_hhdm;
static volatile uint64_t recovery_frame;
/* The handler changes these asynchronously across a faulting volatile load.
 * A compiler must re-read them after architectural iretq. */
static volatile bool recovery_armed;
static volatile unsigned recovery_count;

/* Called only by the IDT #PF handler. Fail closed on any unsolicited fault,
 * wrong CR3, wrong address, protection violation or repeated invocation. */
bool htmlk_paging_recover_page_fault(uint64_t fault_address, uint64_t error) {
    if (!recovery_armed || recovery_count != 0 ||
        fault_address != HTMLK_PAGING_VADDR || error != 0 ||
        recovery_registry == 0 || recovery_table == 0 ||
        recovery_table[0] != 0) return false;
    uint64_t cr3;
    __asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));
    if ((cr3 & HTMLK_PAGING_PHYS_MASK) != recovery_cr3_phys) return false;
    uint64_t phys = UINT64_MAX;
    if (!htmlk_frame_claim(recovery_registry, HTMLK_FRAME_DATA, &phys) ||
        recovery_hhdm > UINT64_MAX - phys - HTMLK_PAGE_SIZE) return false;
    volatile uint64_t *raw = (volatile uint64_t *)(uintptr_t)(recovery_hhdm + phys);
    for (unsigned i = 0; i < HTMLK_PAGE_SIZE / 8; ++i) raw[i] = 0;
    recovery_frame = phys;
    recovery_table[0] = phys | HTMLK_PAGING_ENTRY_RW;
    __asm__ volatile ("invlpg (%0)" : : "r"((uintptr_t)HTMLK_PAGING_VADDR) : "memory");
    recovery_armed = false;
    recovery_count++;
    report("M3_PF_RECOVERED\n");
    return true; /* GCC interrupt ABI emits iretq, CPU retries faulted load. */
}
#endif

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
    struct htmlk_frame_registry registry = {0};
    if (!htmlk_frames_init(&registry, &pool)) {
        failed("M3_PAGING_OWNER_INIT_FAILED\n");
    }
    uint64_t frames[5];
    for (unsigned i = 0; i < 5; ++i) {
        const enum htmlk_frame_owner owner =
            i == 4 ? HTMLK_FRAME_DATA : HTMLK_FRAME_TABLE;
        if (!htmlk_frame_claim(&registry, owner, &frames[i]) ||
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

#ifdef HTMLK_M3_MULTI_PAGE_TEST
    /* Three DATA pages, three independent virtual offsets, three cycles.
     * Prove real CPU/HHDM aliasing, owner reuse and that unmapping one leaf
     * never clobbers the existing first-page mapping.
     */
    uint64_t first_round_frames[3] = {0};
    for (unsigned round = 0; round < 3; ++round) {
        uint64_t added_frames[3];
        for (unsigned i = 0; i < 3; ++i) {
            if (!htmlk_frame_claim(&registry, HTMLK_FRAME_DATA,
                                   &added_frames[i]) ||
                added_frames[i] > HTMLK_PAGING_PHYS_MASK ||
                offset > UINT64_MAX - added_frames[i] - HTMLK_PAGE_SIZE)
                failed("M3_MULTI_FRAME_EXHAUSTED\n");
            if (round == 0) first_round_frames[i] = added_frames[i];
            if (first_round_frames[i] != added_frames[i])
                failed("M3_MULTI_FRAME_REUSE_MISMATCH\n");
            volatile uint64_t *physical =
                (volatile uint64_t *)(uintptr_t)(offset + added_frames[i]);
            *physical = UINT64_C(0x4D334D554C544900) +
                        (uint64_t)round * 16U + (uint64_t)i;
            if (!htmlk_paging_leaf_map(pt, i + 1, added_frames[i]))
                failed("M3_MULTI_MAP_REJECTED\n");
            volatile uint64_t *mapped = (volatile uint64_t *)(uintptr_t)(
                HTMLK_PAGING_VADDR + ((uint64_t)i + 1U) * HTMLK_PAGE_SIZE);
            __asm__ volatile ("invlpg (%0)" : : "r"(mapped) : "memory");
            if (*mapped != *physical)
                failed("M3_MULTI_ALIAS_READ_FAILED\n");
            *mapped ^= UINT64_C(0x5A5A5A5A5A5A5A5A);
            if (*physical !=
                (UINT64_C(0x4D334D554C544900) +
                 (uint64_t)round * 16U + (uint64_t)i) ^
                    UINT64_C(0x5A5A5A5A5A5A5A5A))
                failed("M3_MULTI_ALIAS_WRITE_FAILED\n");
        }
        if (htmlk_paging_leaf_map(pt, 1, added_frames[0]) ||
            htmlk_paging_leaf_map(pt, 4, added_frames[0]) ||
            htmlk_paging_leaf_unmap(pt, 1, added_frames[1]))
            failed("M3_MULTI_UNSAFE_MAP_ACCEPTED\n");
        for (unsigned i = 0; i < 3; ++i) {
            volatile uint64_t *mapped = (volatile uint64_t *)(uintptr_t)(
                HTMLK_PAGING_VADDR + ((uint64_t)i + 1U) * HTMLK_PAGE_SIZE);
            if (!htmlk_paging_leaf_unmap(pt, i + 1, added_frames[i]))
                failed("M3_MULTI_UNMAP_REJECTED\n");
            __asm__ volatile ("invlpg (%0)" : : "r"(mapped) : "memory");
            if (htmlk_paging_leaf_unmap(pt, i + 1, added_frames[i]) ||
                !htmlk_frame_release(&registry, HTMLK_FRAME_DATA,
                                     added_frames[i]))
                failed("M3_MULTI_DOUBLE_RELEASE_ACCEPTED\n");
        }
        if (registry.live != 5 ||
            *virtual_alias != UINT64_C(0x4d33504147454d41) ||
            *physical_alias != UINT64_C(0x4d33504147454d41))
            failed("M3_MULTI_PARENT_ALIAS_DAMAGED\n");
    }
    report("M3_MULTI_PAGE_RECLAIM_OK\n");
#ifdef HTMLK_M3_MULTI_PAGE_FAULT_TEST
    /* An already revoked *second* page must raise a genuine CPU #PF.
     * This address is NOT the approved one-shot recovery address.
     */
    volatile uint64_t *revoked = (volatile uint64_t *)(uintptr_t)(
        HTMLK_PAGING_VADDR + 2U * HTMLK_PAGE_SIZE);
    volatile uint64_t should_fault = *revoked;
    (void)should_fault;
    failed("M3_MULTI_REVOKED_PAGE_STILL_ACCESSIBLE\n");
#endif
#endif


    /* Revoke the private 4KiB virtual alias and invalidate its TLB entry. */
    pt[0] = 0;
    __asm__ volatile ("invlpg (%0)" : : "r"(virtual_alias) : "memory");
    if (pt[0] != 0) failed("M3_PAGING_UNMAP_FAILED\n");
    report("M3_PAGING_UNMAPPED\n");

#ifdef HTMLK_M3_PAGING_UNMAP_FAULT_TEST
    /* Genuine unauthorized #PF must still fail-stop; not auto-recovered. */
    volatile uint64_t must_fault = *virtual_alias;
    (void)must_fault;
    failed("M3_PAGING_BAD_UNMAP_ALLOWED\n");
#elif defined(HTMLK_M3_PAGING_RECOVER_TEST)
    recovery_registry = &registry;
    recovery_table = pt;
    recovery_cr3_phys = frames[0];
    recovery_hhdm = offset;
    recovery_count = 0;
    recovery_frame = 0;
    recovery_armed = true;
    /* The known CPU fault is asynchronous to normal C control flow.
     * Make all ISR-shared state globally observable before the first read. */
    __asm__ volatile ("" : : : "memory");
    /* This actual CPU load #PFs. The IDT installs one zeroed DATA page,
     * iretq retries the load, and execution resumes with value zero. */
    const uint64_t zero = *virtual_alias;
    if (zero != 0)
        failed("M3_PAGING_RECOVERY_NONZERO\n");
    if (recovery_armed)
        failed("M3_PAGING_RECOVERY_STILL_ARMED\n");
    if (recovery_count != 1)
        failed("M3_PAGING_RECOVERY_COUNT_WRONG\n");
    if (recovery_frame == 0)
        failed("M3_PAGING_RECOVERY_FRAME_MISSING\n");
    /* CPU may set Accessed (bit 5) and Dirty (bit 6) on a valid
     * leaf PTE after it retries the fault. Validate physical address
     * and required permissions, not exact raw PTE equality. */
    const uint64_t post_retry_pte = pt[0];
    if ((post_retry_pte & HTMLK_PAGING_PHYS_MASK) != recovery_frame ||
        (post_retry_pte & HTMLK_PAGING_ENTRY_RW) != HTMLK_PAGING_ENTRY_RW ||
        (post_retry_pte & UINT64_C(4)) != 0)
        failed("M3_PAGING_RECOVERY_PTE_MISMATCH\n");
    *virtual_alias = UINT64_C(0x123456789ABCDEF0);
    volatile uint64_t *recovered_phys =
        (volatile uint64_t *)(uintptr_t)(offset + recovery_frame);
    if (*recovered_phys != UINT64_C(0x123456789ABCDEF0))
        failed("M3_PAGING_RECOVERY_ALIAS_BAD\n");
    report("M3_PAGING_RETRY_OK\n");
    pt[0] = 0;
    __asm__ volatile ("invlpg (%0)" : : "r"(virtual_alias) : "memory");
    recovery_table = 0;
    recovery_registry = 0;
#endif
#ifndef HTMLK_M3_PAGING_UNMAP_FAULT_TEST
    __asm__ volatile ("mov %0, %%cr3" : : "r"(old_cr3) : "memory");
    report("M3_PAGING_RESTORED\n");
#ifdef HTMLK_M3_PAGING_RECOVER_TEST
    if (!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, recovery_frame))
        failed("M3_PAGING_RECOVERED_FRAME_LEAK\n");
#endif
    if (!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, frames[4]))
        failed("M3_PAGING_ORIGINAL_FRAME_LEAK\n");
    for (unsigned i = 0; i < 4; ++i) {
        if (!htmlk_frame_release(&registry, HTMLK_FRAME_TABLE, frames[i]))
            failed("M3_PAGING_TABLE_LEAK\n");
    }
    if (registry.live != 0)
        failed("M3_PAGING_OWNER_LEAK\n");
#ifdef HTMLK_M3_OWNED_FRAME_TEST
    /* Actual boot-time negative controls: reclaimed pages are deterministic,
     * double-free/wrong-owner are rejected, 17th claim must fail. */
    uint64_t reclaimed[HTMLK_POOL_PAGES];
    for (unsigned i = 0; i < HTMLK_POOL_PAGES; ++i) {
        if (!htmlk_frame_claim(&registry, HTMLK_FRAME_DATA, &reclaimed[i]) ||
            reclaimed[i] != pool.first_phys + (uint64_t)i * HTMLK_PAGE_SIZE)
            failed("M3_PAGING_RECLAIM_WRONG\n");
    }
    uint64_t sentinel = UINT64_MAX;
    if (htmlk_frame_claim(&registry, HTMLK_FRAME_DATA, &sentinel) ||
        sentinel != UINT64_MAX ||
        htmlk_frame_release(&registry, HTMLK_FRAME_TABLE, reclaimed[0]))
        failed("M3_PAGING_OWNER_NEGATIVE_MISSED\n");
    for (unsigned i = 0; i < HTMLK_POOL_PAGES; ++i) {
        if (!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, reclaimed[i]) ||
            htmlk_frame_release(&registry, HTMLK_FRAME_DATA, reclaimed[i]))
            failed("M3_PAGING_DOUBLE_FREE_ALLOWED\n");
    }
    report("M3_FRAME_OWNERSHIP_OK\n");
#endif
#endif
}
