/* M3 opt-in boot probe: real Limine memory-map inspection and HHDM writes.
 * Never enabled by the ordinary HTML-derived ISO; enabled by --memory-probe.
 */
#include <stdint.h>
#include "limine.h"
#include "memory_probe.h"
#include "page_pool.h"

_Static_assert(LIMINE_MEMMAP_USABLE == HTMLK_REGION_USABLE,
               "Limine and page-pool usable types must match");

static void debug_text(const char *message) {
    while (*message != 0) {
        const unsigned char byte = (unsigned char)*message++;
        __asm__ volatile ("outb %0, %1" : :
                          "a"(byte), "Nd"((unsigned short)0xe9));
    }
}

__attribute__((noreturn))
static void failed(const char *message) {
    debug_text(message);
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0, %1" : :
                      "a"((unsigned char)0x13), "Nd"((unsigned short)0xf4));
#endif
    __asm__ volatile ("cli");
    for (;;) __asm__ volatile ("hlt");
}

void htmlk_memory_probe(const struct limine_memmap_response *map,
                        const struct limine_hhdm_response *hhdm) {
    if (map == 0 || hhdm == 0 || map->entries == 0 ||
        map->entry_count == 0 || map->entry_count > HTMLK_MAX_MEMORY_REGIONS) {
        failed("M3_MEMMAP_MISSING_OR_TOO_LARGE\n");
    }
    struct htmlk_phys_range ranges[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i = 0; i < map->entry_count; ++i) {
        const struct limine_memmap_entry *entry = map->entries[i];
        if (entry == 0) {
            failed("M3_MEMMAP_NULL_ENTRY\n");
        }
        ranges[i].base = entry->base;
        ranges[i].length = entry->length;
        ranges[i].type = entry->type;
    }
#ifdef HTMLK_M3_BAD_MAP_TEST
    /* Negative control: corrupt a stack-local *copy*, never bootloader data. */
    ranges[0].length = 0;
    struct htmlk_page_pool reject;
    if (!htmlk_page_pool_init(ranges, map->entry_count, &reject)) {
        failed("M3_BADMAP_REJECTED\n");
    }
    failed("M3_BADMAP_NOT_REJECTED\n");
#endif
    struct htmlk_page_pool pool;
    if (!htmlk_page_pool_init(ranges, map->entry_count, &pool)) {
        failed("M3_MEMMAP_INVALID\n");
    }
    if ((hhdm->offset & (HTMLK_PAGE_SIZE - 1)) != 0 ||
        hhdm->offset == 0 || hhdm->offset > UINT64_MAX - pool.end_phys) {
        failed("M3_HHDM_INVALID\n");
    }
    debug_text("M3_MEMMAP_VALIDATED\n");

    uint64_t first_page = 0, last_page = 0;
    for (uint64_t i = 0; i < HTMLK_POOL_PAGES; ++i) {
        uint64_t physical = 0;
        if (!htmlk_page_take(&pool, &physical) ||
            physical < pool.first_phys ||
            physical >= pool.end_phys ||
            (physical & (HTMLK_PAGE_SIZE - 1)) != 0) {
            failed("M3_PAGE_ALLOC_INVALID\n");
        }
        if (i == 0) first_page = physical;
        if (i == HTMLK_POOL_PAGES - 1) last_page = physical;
        /* Explicit HHDM mapping: touch each allocated usable physical page.
         * Volatile prevents the compiler eliminating the actual RAM access. */
        volatile uint64_t *value =
            (volatile uint64_t *)(uintptr_t)(hhdm->offset + physical);
        *value = UINT64_C(0x4d334d454d000000) + i;
        if (*value != UINT64_C(0x4d334d454d000000) + i) {
            failed("M3_PAGE_READBACK_FAILED\n");
        }
    }
    if (last_page - first_page !=
        (HTMLK_POOL_PAGES - 1) * HTMLK_PAGE_SIZE) {
        failed("M3_PAGE_NOT_SEQUENTIAL\n");
    }
    debug_text("M3_PAGES_WRITTEN\n");

    uint64_t sentinel = UINT64_MAX;
    if (htmlk_page_take(&pool, &sentinel) || sentinel != UINT64_MAX) {
        failed("M3_POOL_OVERALLOCATED\n");
    }
    debug_text("M3_EXHAUSTION_HANDLED\n");
}
