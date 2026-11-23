/* M3: bounded 16-page owner registry, pure C11 and allocation-policy-only.
 * No implicit dereference of physical addresses; not exposed to HTML user code.
 */
#ifndef HTMLK_FRAME_OWNER_H
#define HTMLK_FRAME_OWNER_H

#include "page_pool.h"

enum htmlk_frame_owner {
    HTMLK_FRAME_FREE = 0,
    HTMLK_FRAME_TABLE = 1,
    HTMLK_FRAME_DATA = 2
};

struct htmlk_frame_registry {
    uint64_t base;
    uint8_t owners[HTMLK_POOL_PAGES];
    uint8_t live;
};

bool htmlk_frames_init(struct htmlk_frame_registry *state,
                       const struct htmlk_page_pool *pool);
bool htmlk_frame_claim(struct htmlk_frame_registry *state,
                       enum htmlk_frame_owner owner, uint64_t *address);
bool htmlk_frame_release(struct htmlk_frame_registry *state,
                         enum htmlk_frame_owner owner, uint64_t address);
#endif
