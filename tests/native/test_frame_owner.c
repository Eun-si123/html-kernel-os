/* Pure C11 frame owner oracle; all assertions execute on actual host memory. */
#include "frame_owner.h"
#include <stdint.h>
#include <stdio.h>

#define CHECK(cond) do { \
    if (!(cond)) { \
        (void)fprintf(stderr, "M3 frame owner failed line %d: %s\n", \
                      __LINE__, #cond); \
        return 1; \
    } \
} while (0)

int main(void) {
    const struct htmlk_phys_range regions[] = {
        {0x1000, 0x40000, 0},
        {0x41000, 0x10000, 1}
    };
    struct htmlk_page_pool pool = {0};
    struct htmlk_frame_registry registry = {0};
    CHECK(htmlk_page_pool_init(regions, 2, &pool));
    CHECK(htmlk_frames_init(&registry, &pool));
    uint64_t phys[HTMLK_POOL_PAGES];
    for (unsigned i = 0; i < HTMLK_POOL_PAGES; ++i) {
        enum htmlk_frame_owner owner = (i < 4) ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
        phys[i] = UINT64_MAX;
        CHECK(htmlk_frame_claim(&registry, owner, &phys[i]));
        CHECK(phys[i] == pool.first_phys + (uint64_t)i * HTMLK_PAGE_SIZE);
    }
    CHECK(registry.live == HTMLK_POOL_PAGES);
    uint64_t sentinel = UINT64_MAX;
    CHECK(!htmlk_frame_claim(&registry, HTMLK_FRAME_DATA, &sentinel));
    CHECK(sentinel == UINT64_MAX);
    CHECK(!htmlk_frame_claim(&registry, HTMLK_FRAME_FREE, &sentinel));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, phys[0]));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_TABLE, phys[5]));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, phys[4] + 1));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, phys[4] + 65536));
    CHECK(htmlk_frame_release(&registry, HTMLK_FRAME_DATA, phys[4]));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_DATA, phys[4]));
    CHECK(registry.live == HTMLK_POOL_PAGES - 1);
    CHECK(htmlk_frame_claim(&registry, HTMLK_FRAME_TABLE, &sentinel));
    CHECK(sentinel == phys[4]); /* precise reclaimed frame, not duplicate */
    CHECK(registry.live == HTMLK_POOL_PAGES);
    CHECK(!htmlk_frame_release(0, HTMLK_FRAME_TABLE, sentinel));
    CHECK(!htmlk_frame_release(&registry, HTMLK_FRAME_FREE, sentinel));
    CHECK(!htmlk_frame_claim(0, HTMLK_FRAME_TABLE, &sentinel));
    CHECK(!htmlk_frame_claim(&registry, HTMLK_FRAME_TABLE, 0));

    CHECK(htmlk_frames_init(&registry, &pool)); /* reset owner bookkeeping */
    CHECK(registry.live == 0);
    CHECK(htmlk_frame_claim(&registry, HTMLK_FRAME_DATA, &sentinel));
    CHECK(sentinel == phys[0]);
    CHECK(!htmlk_frames_init(&registry, 0)); /* MUST fail closed */
    CHECK(registry.live == 0 && registry.base == 0);
    CHECK(!htmlk_frame_claim(&registry, HTMLK_FRAME_DATA, &sentinel));
    CHECK(!htmlk_frames_init(0, &pool));

    struct htmlk_page_pool consumed = pool;
    consumed.next_phys += HTMLK_PAGE_SIZE;
    CHECK(!htmlk_frames_init(&registry, &consumed));
    CHECK(registry.live == 0);
    (void)puts("M3 FRAME OWNERSHIP / REUSE / EXHAUSTION PASS");
    return 0;
}
