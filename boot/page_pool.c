#include "page_pool.h"

/* No memory ownership is inferred from an address range alone:
 * the bootloader must explicitly label it USABLE. */
bool htmlk_page_pool_init(const struct htmlk_phys_range *regions,
                          uint64_t count, struct htmlk_page_pool *pool) {
    if (regions == 0 || pool == 0 ||
        count == 0 || count > HTMLK_MAX_MEMORY_REGIONS) {
        return false;
    }
    for (uint64_t i = 0; i < count; ++i) {
        if (regions[i].length == 0 ||
            regions[i].length > UINT64_MAX - regions[i].base) {
            return false;
        }
    }
    /* Validate the whole map first, including unusable regions. Never
     * hand out a page from an overlapping/ambiguous bootloader response. */
    for (uint64_t i = 0; i < count; ++i) {
        const uint64_t end_i = regions[i].base + regions[i].length;
        for (uint64_t j = i + 1; j < count; ++j) {
            const uint64_t end_j = regions[j].base + regions[j].length;
            if (regions[i].base < end_j && regions[j].base < end_i) {
                return false;
            }
        }
    }
    uint64_t selected = 0;
    uint64_t best_capacity = 0;
    for (uint64_t i = 0; i < count; ++i) {
        if (regions[i].type != HTMLK_REGION_USABLE) {
            continue;
        }
        const uint64_t limit = regions[i].base + regions[i].length;
        const uint64_t remainder = regions[i].base & (HTMLK_PAGE_SIZE - 1);
        const uint64_t padding = remainder ? HTMLK_PAGE_SIZE - remainder : 0;
        if (padding > regions[i].length) {
            continue;
        }
        uint64_t first = regions[i].base + padding;
        if (first < HTMLK_PAGE_SIZE) {
            first = HTMLK_PAGE_SIZE; /* never return physical address zero */
        }
        const uint64_t aligned_end = limit & ~(HTMLK_PAGE_SIZE - 1);
        if (first >= aligned_end) {
            continue;
        }
        const uint64_t capacity = aligned_end - first;
        if (capacity >= HTMLK_POOL_PAGES * HTMLK_PAGE_SIZE &&
            (capacity > best_capacity ||
             (capacity == best_capacity && first < selected))) {
            best_capacity = capacity;
            selected = first;
        }
    }
    if (best_capacity == 0) {
        return false;
    }
    pool->first_phys = selected;
    pool->next_phys = selected;
    pool->end_phys = selected + HTMLK_POOL_PAGES * HTMLK_PAGE_SIZE;
    return true;
}

bool htmlk_page_take(struct htmlk_page_pool *pool, uint64_t *phys_out) {
    if (pool == 0 || phys_out == 0 ||
        pool->first_phys < HTMLK_PAGE_SIZE ||
        (pool->next_phys & (HTMLK_PAGE_SIZE - 1)) != 0 ||
        pool->next_phys > pool->end_phys ||
        pool->end_phys - pool->next_phys < HTMLK_PAGE_SIZE) {
        return false;
    }
    *phys_out = pool->next_phys;
    pool->next_phys += HTMLK_PAGE_SIZE;
    return true;
}
