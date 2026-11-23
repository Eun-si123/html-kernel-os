#include "user_syscall_policy.h"
#include <assert.h>
#include <stdio.h>

#define INIT ((struct htmlk_m5_syscall_provenance){ \
 .frame_address=UINT64_C(0xffffffff80003f60), \
 .tss_rsp0=UINT64_C(0xffffffff80004000), \
 .cs=0x2bU,.ss=0x33U,.rflags=0x202U, \
 .active_cr3=0x2000U,.owned_cr3=0x2000U,.saved_cr3=0x1000U, \
 .saved_main_rsp=UINT64_C(0xffffffff80002000),.live_frames=6U, \
 .has_active_app=true,.already_terminated=false })
int main(void) {
    struct htmlk_m5_syscall_provenance x=INIT;
    assert(htmlk_m5_bad_syscall_frame_is_owned(&x));
    assert(!htmlk_m5_bad_syscall_frame_is_owned(0));
#define NEG(field,value) do { x=INIT; x.field=value; \
     assert(!htmlk_m5_bad_syscall_frame_is_owned(&x)); } while(0)
    NEG(frame_address,UINT64_C(0xffffffff80003f68));
    NEG(tss_rsp0,UINT64_C(0xffffffff80004008));
    NEG(tss_rsp0,UINT64_C(0x0000400000004000));
    NEG(tss_rsp0,UINT64_C(0xffff000000004000));
    NEG(cs,0x8U); NEG(ss,0x10U);
    NEG(rflags,0x200U); NEG(rflags,0x3202U);
    NEG(rflags,0x4202U); NEG(rflags,0x20202U);
    NEG(active_cr3,0x1000U); NEG(owned_cr3,0);
    NEG(owned_cr3,0x2001U); NEG(saved_cr3,0x2000U);
    NEG(saved_cr3,0); NEG(saved_main_rsp,0);
    NEG(saved_main_rsp,UINT64_C(0x0000400000000000));
    NEG(live_frames,5U); NEG(live_frames,7U);
    NEG(has_active_app,false); NEG(already_terminated,true);
    puts("M5-E3-C MALFORMED USER SYSCALL ORIGIN/OWNERSHIP GUARD PASS");
    return 0;
}
