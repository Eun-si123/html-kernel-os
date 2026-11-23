/* Pure host-testable part of the x86-64 CPL3 IRQ frame contract. */
#include "preempt_user.h"
#include "user_pages.h"
bool htmlk_m4_d_arch_frame_valid(const struct htmlk_m4_d_frame *f,
                                 unsigned task,uint64_t bytes) {
    if (!f || task>=HTMLK_M4_D_TASKS ||
        bytes==0 || bytes>4096 ||
        f->cs!=0x2bU || f->ss!=0x33U ||
        f->rip<HTMLK_M4_USER_BASE ||
        f->rip-HTMLK_M4_USER_BASE>=bytes ||
        f->rsp<=HTMLK_M4_USER_STACK-4096U ||
        f->rsp>HTMLK_M4_USER_STACK ||
        (f->rflags & (1ULL<<9))==0 ||
        (f->rflags & (3ULL<<12))!=0 ||
        f->rbx!=(task==0U?HTMLK_M4_D_A_RBX:HTMLK_M4_D_B_RBX) ||
        f->r12!=(task==0U?HTMLK_M4_D_A_R12:HTMLK_M4_D_B_R12) ||
        f->r10!=(task==0U?HTMLK_M4_D_A_R10:HTMLK_M4_D_B_R10) ||
        f->r13!=(task==0U?HTMLK_M4_D_A_RBX:HTMLK_M4_D_B_RBX))
        return false;
    return true;
}
