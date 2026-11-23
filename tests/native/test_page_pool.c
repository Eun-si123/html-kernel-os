/* Host-side C11 boundary oracle for the physical page pool.
 * Built and run by scripts/test_m3_memory.py under GCC UBSan -O0/-O3.
 */
#include <stdint.h>
#include <stdio.h>
#include "page_pool.h"

#define CHECK(value) do { \
    if (!(value)) { \
        (void)fprintf(stderr, "page pool check failed at %d: %s\\n", __LINE__, #value); \
        return 1; \
    } \
} while (0)

int main(void) {
    const struct htmlk_phys_range valid[] = {
        {0, 0x1000, 1},             /* reserved first page */
        {0x1000, 0x20000, 0},       /* usable 32 x 4KiB */
        {0x21000, 0x10000, 1},      /* reserved after usable */
    };
    struct htmlk_page_pool pool = {0};
    CHECK(htmlk_page_pool_init(valid, 3, &pool));
    CHECK(pool.first_phys == 0x1000);
    CHECK(pool.end_phys == 0x11000);
    for (uint64_t i = 0; i < HTMLK_POOL_PAGES; ++i) {
        uint64_t p = UINT64_MAX;
        CHECK(htmlk_page_take(&pool, &p));
        CHECK(p == 0x1000 + 4096 * i);
        CHECK(p >= valid[1].base && p + 4096 <= valid[1].base + valid[1].length);
    }
    uint64_t sentinel = UINT64_MAX;
    CHECK(!htmlk_page_take(&pool, &sentinel));
    CHECK(sentinel == UINT64_MAX);

    const struct htmlk_phys_range unaligned[] = {
        {0x1801, 0x20000, 0}
    };
    CHECK(htmlk_page_pool_init(unaligned, 1, &pool));
    CHECK(pool.first_phys == 0x2000);

    const struct htmlk_phys_range zero_guard[] = {
        {0, 0x20000, 0}
    };
    CHECK(htmlk_page_pool_init(zero_guard, 1, &pool));
    CHECK(pool.first_phys == 0x1000);

    const struct htmlk_phys_range reserved[] = {
        {0x1000, 0x20000, 1}
    };
    CHECK(!htmlk_page_pool_init(reserved, 1, &pool));
    const struct htmlk_phys_range too_small[] = {
        {0x1000, 0xF000, 0}
    };
    CHECK(!htmlk_page_pool_init(too_small, 1, &pool));
    const struct htmlk_phys_range empty[] = {
        {0x1000, 0, 0}
    };
    CHECK(!htmlk_page_pool_init(empty, 1, &pool));
    const struct htmlk_phys_range wrap[] = {
        {UINT64_MAX - 10, 12, 0}
    };
    CHECK(!htmlk_page_pool_init(wrap, 1, &pool));
    const struct htmlk_phys_range overlap[] = {
        {0x1000, 0x20000, 0}, {0x9000, 0x10000, 1}
    };
    CHECK(!htmlk_page_pool_init(overlap, 2, &pool));
    CHECK(!htmlk_page_pool_init(valid, 0, &pool));
    CHECK(!htmlk_page_pool_init(valid, 129, &pool)); /* no reads beyond bounds */
    CHECK(!htmlk_page_pool_init(0, 1, &pool));
    CHECK(!htmlk_page_pool_init(valid, 3, 0));
    CHECK(!htmlk_page_take(0, &sentinel));
    CHECK(!htmlk_page_take(&pool, 0));
    (void)puts("M3 PAGE POOL HOST CONTRACT PASS");
    return 0;
}
