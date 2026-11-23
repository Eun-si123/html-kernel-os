/* M3: deliberately small, testable physical-page pool contract.
 * Pure C11: no IO, libc, heap allocation or implicit physical memory access.
 */
#ifndef HTMLK_PAGE_POOL_H
#define HTMLK_PAGE_POOL_H

#include <stdbool.h>
#include <stdint.h>

#define HTMLK_PAGE_SIZE UINT64_C(4096)
#define HTMLK_POOL_PAGES UINT64_C(16)
#define HTMLK_MAX_MEMORY_REGIONS UINT64_C(128)
#define HTMLK_REGION_USABLE UINT64_C(0)

struct htmlk_phys_range {
    uint64_t base;
    uint64_t length;
    uint64_t type;
};

struct htmlk_page_pool {
    uint64_t first_phys;
    uint64_t next_phys;
    uint64_t end_phys; /* exclusive */
};

/* Returns false on empty, malformed, overlapping, overflowing or insufficient
 * maps. Only the type-0 USABLE region is ever allocatable. The pool is exactly
 * 16 x 4KiB aligned pages; metadata is kept outside the selected pages.
 */
bool htmlk_page_pool_init(const struct htmlk_phys_range *regions,
                          uint64_t count, struct htmlk_page_pool *pool);

/* Returns false when exhausted. Never returns a physical page twice. */
bool htmlk_page_take(struct htmlk_page_pool *pool, uint64_t *phys_out);

#endif
