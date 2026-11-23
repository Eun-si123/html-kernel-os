#include "frame_owner.h"

static bool supported(enum htmlk_frame_owner owner) {
    return owner == HTMLK_FRAME_TABLE || owner == HTMLK_FRAME_DATA;
}

bool htmlk_frames_init(struct htmlk_frame_registry *state,
                       const struct htmlk_page_pool *pool) {
    if (state == 0) return false;
    state->base = 0;
    state->live = 0;
    for (unsigned i = 0; i < HTMLK_POOL_PAGES; ++i) state->owners[i] = 0;
    if (pool == 0 || pool->first_phys < HTMLK_PAGE_SIZE ||
        (pool->first_phys & (HTMLK_PAGE_SIZE - 1)) != 0 ||
        pool->first_phys > UINT64_MAX - HTMLK_POOL_PAGES * HTMLK_PAGE_SIZE ||
        pool->next_phys != pool->first_phys ||
        pool->end_phys != pool->first_phys + HTMLK_POOL_PAGES * HTMLK_PAGE_SIZE) {
        return false;
    }
    state->base = pool->first_phys;
    return true;
}

bool htmlk_frame_claim(struct htmlk_frame_registry *state,
                       enum htmlk_frame_owner owner, uint64_t *address) {
    if (state == 0 || address == 0 || state->base < HTMLK_PAGE_SIZE ||
        !supported(owner) || state->live >= HTMLK_POOL_PAGES) return false;
    for (unsigned i = 0; i < HTMLK_POOL_PAGES; ++i) {
        if (state->owners[i] == HTMLK_FRAME_FREE) {
            state->owners[i] = (uint8_t)owner;
            ++state->live;
            *address = state->base + (uint64_t)i * HTMLK_PAGE_SIZE;
            return true;
        }
    }
    return false;
}

bool htmlk_frame_release(struct htmlk_frame_registry *state,
                         enum htmlk_frame_owner owner, uint64_t address) {
    if (state == 0 || !supported(owner) ||
        state->base < HTMLK_PAGE_SIZE ||
        state->live == 0 ||
        address < state->base ||
        address - state->base >= HTMLK_POOL_PAGES * HTMLK_PAGE_SIZE ||
        ((address - state->base) & (HTMLK_PAGE_SIZE - 1)) != 0) return false;
    const uint64_t idx = (address - state->base) / HTMLK_PAGE_SIZE;
    if (state->owners[idx] != (uint8_t)owner) return false;
    state->owners[idx] = HTMLK_FRAME_FREE;
    --state->live;
    return true;
}
