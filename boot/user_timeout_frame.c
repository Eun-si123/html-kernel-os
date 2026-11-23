#include "user_timeout_frame.h"
#include "user_pages.h"
#include "user_image.h"
#include "page_pool.h"
#include <stdint.h>

bool htmlk_m5_timeout_frame_valid(const struct htmlk_m4_d1_irq_frame *f,
                                   uint64_t rsp0, uint64_t code_length,
                                   uint64_t current_cr3, uint64_t user_cr3) {
    if (!f || rsp0 < sizeof(*f) || (rsp0 & 15U) != 0 ||
        current_cr3 != user_cr3 || user_cr3 == 0 ||
        (user_cr3 & 4095U) != 0 ||
        code_length == 0 || code_length > HTMLK_HKE_MAX_CODE_BYTES ||
        (uint64_t)(uintptr_t)f != rsp0 - sizeof(*f) ||
        f->cs != UINT64_C(0x2b) || f->ss != UINT64_C(0x33) ||
        f->rip < HTMLK_M4_USER_BASE ||
        f->rip - HTMLK_M4_USER_BASE >= code_length ||
        f->rsp <= HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE ||
        f->rsp > HTMLK_M4_USER_STACK ||
        (f->rflags & UINT64_C(0x202)) != UINT64_C(0x202) ||
        (f->rflags & (UINT64_C(3)<<12 | UINT64_C(1)<<14 |
                      UINT64_C(1)<<17)) != 0) return false;
    return true;
}
