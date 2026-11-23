#include "user_fault_policy.h"
#include "user_pages.h"
#include <stdint.h>
#include <assert.h>
#include <stdio.h>

static bool ok(unsigned vec,uint64_t rip,uint64_t cs,uint64_t flags,
               uint64_t rsp,uint64_t ss,uint64_t err,uint64_t cr3,
               uint64_t root,uint64_t len) {
    return htmlk_m5_user_fault_frame_valid(vec,rip,cs,flags,rsp,ss,err,
                                            cr3,root,len);
}
#define GOOD(v,e) ok(v,HTMLK_M4_USER_BASE,0x2bU,0x2U,HTMLK_M4_USER_STACK-16U,0x33U,e,0x2000U,0x2000U,64U)
int main(void) {
    assert(GOOD(0U,0)); assert(GOOD(1U,0)); assert(GOOD(3U,0));
    assert(GOOD(6U,0)); assert(GOOD(13U,0));
    assert(GOOD(14U,4)); assert(GOOD(14U,5));
    assert(GOOD(14U,6)); assert(GOOD(14U,7));
    assert(!GOOD(14U,0)); assert(!GOOD(14U,1));
    assert(!GOOD(14U,0x84)); assert(!GOOD(13U,1));
    assert(!GOOD(0U,1)); assert(!GOOD(1U,1)); assert(!GOOD(3U,1));
    assert(ok(1U,HTMLK_M4_USER_BASE+64,0x2b,2,HTMLK_M4_USER_STACK-16,
              0x33,0,0x2000,0x2000,64)); /* INT1 trap at end */
    assert(ok(3U,HTMLK_M4_USER_BASE+64,0x2b,2,HTMLK_M4_USER_STACK-16,
              0x33,0,0x2000,0x2000,64)); /* INT3 trap at end */
    assert(!ok(0U,HTMLK_M4_USER_BASE+64,0x2b,2,HTMLK_M4_USER_STACK-16,
               0x33,0,0x2000,0x2000,64)); /* divide fault needs exact RIP */
    assert(!ok(3U,HTMLK_M4_USER_BASE+65,0x2b,2,HTMLK_M4_USER_STACK-16,
               0x33,0,0x2000,0x2000,64));
    assert(!GOOD(6U,4)); assert(!GOOD(8U,0));
    /* Shared CPL3 owner checks must apply equally to each new CPU trap. */
    const unsigned extra_vectors[] = {0U, 1U, 3U};
    for (unsigned i=0; i<3U; ++i) {
        const unsigned vec=extra_vectors[i];
        assert(!ok(vec,HTMLK_M4_USER_BASE,0x08,2,HTMLK_M4_USER_STACK-16,
                   0x33,0,0x2000,0x2000,64));
        assert(!ok(vec,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,
                   0x33,0,0x3000,0x2000,64));
        assert(!ok(vec,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_BASE+4096,
                   0x33,0,0x2000,0x2000,64));
        assert(!ok(vec,HTMLK_M4_USER_BASE,0x2b,0x3002,
                   HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    }
    assert(!ok(13,HTMLK_M4_USER_BASE,0x08,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x10,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,0x3002,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,0x4002,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,0x20002,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE-1,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE+64,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_BASE+4096,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK+1,0x33,0,0x2000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x3000,0x2000,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2001,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0,64));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,0));
    assert(!ok(13,HTMLK_M4_USER_BASE,0x2b,2,HTMLK_M4_USER_STACK-16,0x33,0,0x2000,0x2000,4096));
    /* M5-E3-E: separate CPU five-word #UD frame on exact trusted RSP0.
     * Never mistake the older 160-byte syscall/IRQ frame for an exception;
     * reject an unowned/forged kernel CS, wrong CR3, or valid user RSP. */
    assert(htmlk_m5_bad_noerr_fault_vector(0U));
    assert(htmlk_m5_bad_noerr_fault_vector(6U));
    for (unsigned vector=1;vector<=31;++vector) {
        if (vector!=6U) assert(!htmlk_m5_bad_noerr_fault_vector(vector));
    }
    const uint64_t user_base = HTMLK_M4_USER_BASE;
    struct htmlk_m5_bad_noerr_owner ud = {
        .frame_address=UINT64_C(0xffff800000200000)-40U,
        .tss_rsp0=UINT64_C(0xffff800000200000),
        .rip=user_base+3U, .cs=0x2bU,.ss=0x33U,.rflags=0x202U,
        .user_rsp=0U,
        .active_cr3=0x2000U,.owned_cr3=0x2000U,
        .saved_cr3=0x3000U,.saved_main_rsp=UINT64_C(0xffff800000300000),
        .code_bytes=64U,.live_frames=6U,
        .has_active_app=true,.already_terminated=false,.expected_if=true,
    };
    assert(htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.user_rsp=user_base+4096U;
    assert(htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.user_rsp=HTMLK_M4_USER_STACK+1U;
    assert(htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.user_rsp=HTMLK_M4_USER_STACK-16U;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.user_rsp=0U;
    ud.expected_if=false;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.rflags=2U;assert(htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.expected_if=true;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.rflags=0x202U;
    ud.cs=0x8U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.cs=0x2bU;
    ud.ss=0x10U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.ss=0x33U;
    ud.frame_address-=8U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.frame_address+=8U;
    ud.frame_address=ud.tss_rsp0-160U;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.frame_address=ud.tss_rsp0-40U;
    ud.rip=user_base+64U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.rip=user_base+3U;
    ud.rip=user_base-1U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.rip=user_base+3U;
    ud.rflags|=UINT64_C(3)<<12;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.rflags=0x202U;
    ud.rflags|=UINT64_C(1)<<14;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.rflags=0x202U;
    ud.rflags|=UINT64_C(1)<<17;
    assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.rflags=0x202U;
    ud.active_cr3=0x3000U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.active_cr3=0x2000U;
    ud.owned_cr3=0x2001U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.owned_cr3=0x2000U;
    ud.saved_cr3=0x2000U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.saved_cr3=0x3000U;
    ud.saved_main_rsp=0U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.saved_main_rsp=UINT64_C(0xffff800000300000);
    ud.tss_rsp0=0U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    ud.tss_rsp0=UINT64_C(0xffff800000200000);
    ud.live_frames=5U;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.live_frames=6U;
    ud.has_active_app=false;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));ud.has_active_app=true;
    ud.already_terminated=true;assert(!htmlk_m5_bad_noerr_stack_owned(&ud));
    assert(!htmlk_m5_bad_noerr_stack_owned(NULL));
    puts("M5-E1 USER EXCEPTION FRAME/CR3/SEL/ERR GUARDS PASS");
}
