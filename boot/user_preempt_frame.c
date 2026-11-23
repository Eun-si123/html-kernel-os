#include "user_preempt_frame.h"
#include "user_pages.h"
#include "page_pool.h"
#include <stdint.h>

bool htmlk_m4_d1_frame_guard(const struct htmlk_m4_d1_irq_frame *f,
                            uintptr_t bottom, uintptr_t top,
                            uint64_t code_len, uint64_t loop_offset,
                            uint64_t rbx, uint64_t r12) {
    if (!f || code_len==0 || code_len>HTMLK_PAGE_SIZE ||
        loop_offset>=code_len || top<=bottom ||
        top-bottom<sizeof(*f)) return false;
    const uintptr_t p=(uintptr_t)f;
    if (p<bottom || p>top-sizeof(*f) || (p&7U)) return false;
    if (f->cs!=0x2bU || f->ss!=0x33U ||
        f->rip<HTMLK_M4_USER_BASE ||
        f->rip-HTMLK_M4_USER_BASE>=code_len ||
        f->rsp<=HTMLK_M4_USER_BASE+HTMLK_PAGE_SIZE ||
        f->rsp>HTMLK_M4_USER_STACK ||
        (f->rflags&0x202U)!=0x202U) return false;
    if (f->rip>=HTMLK_M4_USER_BASE+loop_offset &&
        (f->rbx!=rbx || f->r12!=r12)) return false;
    return true;
}
