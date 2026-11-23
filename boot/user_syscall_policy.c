#include "user_syscall_policy.h"
#include <stdint.h>

bool htmlk_m5_bad_syscall_frame_is_owned(
    const struct htmlk_m5_syscall_provenance *c) {
    if (!c || !c->has_active_app || c->already_terminated ||
        c->live_frames!=6U ||
        c->tss_rsp0<160U || (c->tss_rsp0&15U) != 0 ||
        (c->tss_rsp0>>48U) != UINT64_C(0xffff) ||
        (c->tss_rsp0 & (UINT64_C(1)<<47)) == 0 ||
        c->frame_address != c->tss_rsp0-160U ||
        c->cs!=0x2bU || c->ss!=0x33U ||
        (c->rflags&UINT64_C(2)) == 0 ||
        (c->rflags&(UINT64_C(3)<<12 | UINT64_C(1)<<14 |
                    UINT64_C(1)<<17)) != 0 ||
        c->owned_cr3==0 || (c->owned_cr3 & 4095U) != 0 ||
        c->active_cr3 != c->owned_cr3 ||
        c->saved_cr3==0 || c->saved_cr3==c->owned_cr3 ||
        c->saved_main_rsp==0 || (c->saved_main_rsp>>48U)!=UINT64_C(0xffff) ||
        (c->saved_main_rsp & (UINT64_C(1)<<47)) == 0)
        return false;
    return true;
}
