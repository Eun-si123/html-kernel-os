#include "user_preempt_policy.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
static const uint64_t v=HTMLK_M4_USER_BASE;
static const uint64_t stack=HTMLK_M4_USER_STACK-16U;
static const uint64_t root=UINT64_C(0x100000);
static bool good(uint64_t rip,uint64_t cs,uint64_t flags,
                 uint64_t rsp,uint64_t ss,uint64_t cr3,
                 uint64_t expected,uint64_t length) {
    return htmlk_m4_d_user_frame_valid(rip,cs,flags,rsp,ss,cr3,
                                       expected,length);
}
int main(void) {
    assert(good(v,0x2b,0x202,stack,0x33,root,root,200U));
    assert(good(v+199U,0x2b,0x202,stack,0x33,root,root,200U));
    assert(!good(v+200U,0x2b,0x202,stack,0x33,root,root,200U));
    assert(!good(v-1U,0x2b,0x202,stack,0x33,root,root,200U));
    assert(!good(v,0x08,0x202,stack,0x33,root,root,200U));
    assert(!good(v,0x2b,0x202,stack,0x10,root,root,200U));
    assert(!good(v,0x2b,0x002,stack,0x33,root,root,200U));
    assert(!good(v,0x2b,0x3202,stack,0x33,root,root,200U));
    assert(!good(v,0x2b,0x202,0U,0x33,root,root,200U));
    assert(!good(v,0x2b,0x202,HTMLK_M4_USER_STACK+1U,
                 0x33,root,root,200U));
    assert(!good(v,0x2b,0x202,stack,0x33,root,root+4096U,200U));
    assert(!good(v,0x2b,0x202,stack,0x33,root+1U,root+1U,200U));
    assert(!good(v,0x2b,0x202,stack,0x33,root,root,0U));
    assert(!good(v,0x2b,0x202,stack,0x33,root,root,4097U));
    assert(htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(1U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,13U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,7U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS+4096U,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x08,0x202,stack,0x33,root,root,200U,3U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,2U,3U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root,200U,3U,2U));
    assert(!htmlk_m4_d_fault_valid(0U,14U,5U,HTMLK_M4_D_BAD_ADDRESS,
        v+160U,0x2b,0x202,stack,0x33,root,root+4096U,200U,3U,3U));
    puts("M4-D REAL CPL3 FRAME/FALLBACK PREDICATES UBSAN PASS");
}
