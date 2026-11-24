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
    /* #GP uses an error-code word at -48 and IRET frame at -40.
     * A five-word #UD frame may not be mistaken for a six-word #GP. */
    struct htmlk_m5_bad_gp_owner gp = {
        .frame=ud,
        .error_word_address=UINT64_C(0xffff800000200000)-48U,
        .error_code=0U,
    };
    gp.frame.already_terminated=false;
    assert(htmlk_m5_bad_gp_stack_owned(&gp));
    gp.error_code=1U;assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.error_code=0U;
    gp.error_code=4U;assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.error_code=0U;
    gp.error_word_address+=8U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.error_word_address-=8U;
    gp.error_word_address-=8U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.error_word_address+=8U;
    gp.frame.frame_address=gp.frame.tss_rsp0-48U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));
    gp.frame.frame_address=gp.frame.tss_rsp0-40U;
    gp.frame.cs=0x08U;assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.cs=0x2bU;
    gp.frame.ss=0x10U;assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.ss=0x33U;
    gp.frame.user_rsp=HTMLK_M4_USER_STACK-16U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.user_rsp=0U;
    gp.frame.rip=HTMLK_M4_USER_BASE+64U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.rip=HTMLK_M4_USER_BASE+3U;
    gp.frame.active_cr3=0x3000U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.active_cr3=0x2000U;
    gp.frame.live_frames=5U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.live_frames=6U;
    gp.frame.already_terminated=true;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.already_terminated=false;
    gp.frame.has_active_app=false;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.has_active_app=true;
    gp.frame.expected_if=false;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.expected_if=true;
    gp.frame.rflags=0x3002U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));gp.frame.rflags=0x202U;
    gp.frame.saved_main_rsp=0U;
    assert(!htmlk_m5_bad_gp_stack_owned(&gp));
    gp.frame.saved_main_rsp=UINT64_C(0xffff800000300000);
    assert(!htmlk_m5_bad_gp_stack_owned(NULL));

    /* M5-E3-H: #PF has an ERROR word and MUST use trusted IST2 (not RSP0).
     * The shared owner gate alone never substitutes for exact IST2 frame. */
    ud.already_terminated=false;
    struct htmlk_m5_bad_pf_owner pf = {
        .frame=ud,
        .ist2_top=ud.tss_rsp0,
        .error_word_address=ud.tss_rsp0-48U,
        .error_code=5U,
        .cr2=UINT64_C(0xffffffff80001000),
    };
    assert(htmlk_m5_bad_pf_stack_owned(&pf));
    pf.error_code=7U;pf.cr2=user_base;
    assert(htmlk_m5_bad_pf_stack_owned(&pf));
    pf.cr2=user_base+4095U;assert(htmlk_m5_bad_pf_stack_owned(&pf));
    pf.cr2=user_base+4096U;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
    pf.error_code=5U;pf.cr2=UINT64_C(0xffffffff80001000);
    for (unsigned bad_error=0;bad_error<128U;++bad_error) {
        if (bad_error==5U || bad_error==7U) continue;
        pf.error_code=bad_error;
        assert(!htmlk_m5_bad_pf_stack_owned(&pf));
    }
    /* E3-J: exactly one unmapped page above the private stack, data only. */
    pf.cr2=HTMLK_M4_USER_STACK;
    for (unsigned err=0;err<128U;++err) {
        pf.error_code=err;
        assert(htmlk_m5_bad_pf_stack_owned(&pf)==(err==4U || err==6U));
    }
    for (unsigned err=4U;err<=6U;err+=2U) {
        pf.error_code=err;
        pf.cr2=HTMLK_M4_USER_STACK+4095U;assert(htmlk_m5_bad_pf_stack_owned(&pf));
        pf.cr2=HTMLK_M4_USER_STACK+4096U;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
        pf.cr2=HTMLK_M4_USER_STACK-1U;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
        pf.cr2=HTMLK_M4_USER_STACK;
        pf.frame.active_cr3=pf.frame.saved_cr3;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
        pf.frame.active_cr3=pf.frame.owned_cr3;
        pf.frame.user_rsp=HTMLK_M4_USER_STACK-16U;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
        pf.frame.user_rsp=0U;
        pf.frame.already_terminated=true;assert(!htmlk_m5_bad_pf_stack_owned(&pf));
        pf.frame.already_terminated=false;
        pf.error_word_address-=8U;assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.error_word_address+=8U;
    }
    pf.error_code=5U;pf.cr2=user_base;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));
    pf.cr2=UINT64_C(0xffffffff80001000);
    pf.error_word_address-=8U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.error_word_address+=8U;
    pf.frame.frame_address-=8U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.frame_address+=8U;
    pf.ist2_top+=16U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.ist2_top-=16U;
    pf.frame.tss_rsp0+=16U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.tss_rsp0-=16U;
    pf.frame.cs=0x08U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.cs=0x2bU;
    pf.frame.ss=0x10U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.ss=0x33U;
    pf.frame.active_cr3=pf.frame.saved_cr3;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.active_cr3=pf.frame.owned_cr3;
    pf.frame.live_frames=5U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.live_frames=6U;
    pf.frame.has_active_app=false;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.has_active_app=true;
    pf.frame.already_terminated=true;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.already_terminated=false;
    pf.frame.user_rsp=HTMLK_M4_USER_STACK-16U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.user_rsp=0U;
    pf.frame.rflags|=UINT64_C(3)<<12;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.rflags=0x202U;
    pf.frame.rip=user_base+64U;
    assert(!htmlk_m5_bad_pf_stack_owned(&pf));pf.frame.rip=user_base+3U;
    assert(!htmlk_m5_bad_pf_stack_owned(NULL));
    /* NX stack instruction fetch must prove exact IST2 provenance and
     * matching stack RIP/CR2, never a generic out-of-code RIP recovery. */
    struct htmlk_m5_bad_pf_owner nx = pf;
    nx.error_code=21U;
    nx.cr2=user_base+4096U;
    nx.frame.rip=nx.cr2;
    nx.frame.user_rsp=HTMLK_M4_USER_STACK-16U;
    assert(htmlk_m5_nx_stack_fault_owned(&nx));
    nx.frame.user_rsp=0U;
    assert(htmlk_m5_nx_stack_fault_owned(&nx));
    for (unsigned e=0;e<128U;++e) {
        nx.error_code=e;
        assert(htmlk_m5_nx_stack_fault_owned(&nx)==(e==21U));
    }
    nx.error_code=21U;
    nx.cr2=HTMLK_M4_USER_STACK-1U;nx.frame.rip=nx.cr2;
    assert(htmlk_m5_nx_stack_fault_owned(&nx));
    nx.cr2=HTMLK_M4_USER_STACK;nx.frame.rip=nx.cr2;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));
    nx.cr2=user_base+4095U;nx.frame.rip=nx.cr2;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));
    nx.cr2=user_base+4096U;nx.frame.rip=nx.cr2+1U;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.frame.rip=nx.cr2;
    nx.frame.cs=8U;assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.frame.cs=0x2bU;
    nx.frame.active_cr3=nx.frame.saved_cr3;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.frame.active_cr3=nx.frame.owned_cr3;
    nx.frame.has_active_app=false;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.frame.has_active_app=true;
    nx.frame.already_terminated=true;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.frame.already_terminated=false;
    nx.error_word_address-=8U;
    assert(!htmlk_m5_nx_stack_fault_owned(&nx));nx.error_word_address+=8U;
    assert(!htmlk_m5_bad_pf_stack_owned(&nx));
    assert(!htmlk_m5_nx_stack_fault_owned(NULL));
    /* M5-E3-I: a genuine ICEBP/INT3 saves RIP AFTER the trap opcode.
     * Only #DB/#BP may accept one-past-code-end with an exactly positioned
     * 40-byte CPU frame, known active CR3 and *bad* user RSP. */
    struct htmlk_m5_bad_noerr_owner trap = ud;
    trap.rip=user_base+64U;
    trap.code_bytes=64U;
    assert(htmlk_m5_bad_trap_stack_owned(1U,&trap));
    assert(htmlk_m5_bad_trap_stack_owned(3U,&trap));
    assert(!htmlk_m5_bad_noerr_stack_owned(&trap));
    for (unsigned vec=0;vec<=31U;++vec) {
        if (vec!=1U && vec!=3U)
            assert(!htmlk_m5_bad_trap_stack_owned(vec,&trap));
    }
    trap.rip=user_base+65U;
    assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));
    trap.rip=user_base;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));
    trap.rip=user_base+1U;
    assert(htmlk_m5_bad_trap_stack_owned(1U,&trap));
    trap.frame_address-=8U;
    assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.frame_address+=8U;
    trap.frame_address=trap.tss_rsp0-160U;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));trap.frame_address=trap.tss_rsp0-40U;
    trap.cs=0x08U;assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.cs=0x2bU;
    trap.ss=0x10U;assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));trap.ss=0x33U;
    trap.user_rsp=HTMLK_M4_USER_STACK-16U;
    assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.user_rsp=0U;
    trap.active_cr3=trap.saved_cr3;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));trap.active_cr3=trap.owned_cr3;
    trap.live_frames=5U;assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.live_frames=6U;
    trap.has_active_app=false;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));trap.has_active_app=true;
    trap.already_terminated=true;
    assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.already_terminated=false;
    trap.expected_if=false;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));trap.expected_if=true;
    trap.rflags=0x3002U;
    assert(!htmlk_m5_bad_trap_stack_owned(1U,&trap));trap.rflags=0x202U;
    trap.saved_main_rsp=0;
    assert(!htmlk_m5_bad_trap_stack_owned(3U,&trap));
    assert(!htmlk_m5_bad_trap_stack_owned(1U,NULL));
    puts("M5-E1 USER EXCEPTION FRAME/CR3/SEL/ERR GUARDS PASS");
}
