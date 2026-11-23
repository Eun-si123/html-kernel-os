#include "user_preempt_policy.h"
bool htmlk_m4_d_user_frame_valid(uint64_t rip, uint64_t cs, uint64_t flags,
    uint64_t rsp, uint64_t ss, uint64_t cr3, uint64_t root,
    uint64_t image_length) {
    return cs == HTMLK_M4_D_USER_CS && ss == HTMLK_M4_D_USER_SS &&
        (flags & UINT64_C(0x202)) == UINT64_C(0x202) &&
        (flags & UINT64_C(0x3400)) == 0 &&
        rip >= HTMLK_M4_USER_BASE && image_length > 0 &&
        image_length <= UINT64_C(4096) &&
        rip - HTMLK_M4_USER_BASE < image_length &&
        rsp >= HTMLK_M4_USER_BASE + UINT64_C(4096) + UINT64_C(32) &&
        rsp <= HTMLK_M4_USER_STACK &&
        (cr3 & UINT64_C(0xfff)) == 0 &&
        cr3 == root && root != 0 &&
        (root & ~HTMLK_M4_USER_PHYS_MASK) == 0;
}
bool htmlk_m4_d_fault_valid(unsigned task, unsigned vector, uint64_t error,
    uint64_t cr2, uint64_t rip, uint64_t cs, uint64_t flags,
    uint64_t rsp, uint64_t ss, uint64_t cr3, uint64_t root,
    uint64_t image_length, unsigned a_steps, unsigned b_steps) {
    return task == 0U && vector == 14U && error == 5U &&
        cr2 == HTMLK_M4_D_BAD_ADDRESS && a_steps >= 3U && b_steps >= 3U &&
        htmlk_m4_d_user_frame_valid(rip,cs,flags,rsp,ss,cr3,root,
                                    image_length);
}
