#include "user_timer_policy.h"
#include "isolation_policy.h"
#include "user_pages.h"
#include "page_pool.h"
#include <stddef.h>
#include <stdint.h>
bool htmlk_m4_d_frame_valid(const struct htmlk_m4_irq_frame *f,
                           uintptr_t lo, uint64_t size, uint64_t code_size) {
    if (!f || size < 512U || size > 16384U || !code_size ||
        code_size > HTMLK_PAGE_SIZE || lo > UINTPTR_MAX - size)
        return false;
    const uintptr_t p = (uintptr_t)f;
    const uintptr_t hi = lo + size;
    if (p < lo + 64U || p > hi - sizeof(*f) || (p & 7U) != 0)
        return false;
    if (f->cs != HTMLK_M4_ISO_USER_CS ||
        f->ss != HTMLK_M4_ISO_USER_SS ||
        f->rip < HTMLK_M4_USER_BASE ||
        f->rip - HTMLK_M4_USER_BASE >= code_size ||
        f->rsp <= HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE ||
        f->rsp > HTMLK_M4_USER_STACK ||
        (f->rflags & 0x202U) != 0x202U ||
        (f->rflags & (3U << 12)) != 0)
        return false;
    return true;
}
