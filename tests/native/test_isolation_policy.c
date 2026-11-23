#include "isolation_policy.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>

static bool check(unsigned vector, unsigned expected, unsigned proc,
 uint64_t rip, uint64_t cs, uint64_t rsp, uint64_t ss, uint64_t error,
 uint64_t cr2, uint64_t current, uint64_t target, uint64_t bytes,
 uint64_t wanted_error, uint64_t wanted_cr2) {
    return htmlk_m4_iso_fault_valid(vector,expected,proc,rip,cs,rsp,ss,
        error,cr2,current,target,bytes,wanted_error,wanted_cr2);
}
int main(void) {
    const uint64_t rip = HTMLK_M4_ISO_USER_START + 24U;
    const uint64_t rsp = HTMLK_M4_ISO_USER_STACK - 16U;
    const uint64_t cs = HTMLK_M4_ISO_USER_CS;
    const uint64_t ss = HTMLK_M4_ISO_USER_SS;
    const uint64_t k = HTMLK_M4_ISO_BAD_KERNEL_ADDRESS;
    const uint64_t p = UINT64_C(0x0000000012345000);
    #define VALID(v,e,proc,addr,selector,stack,seg,err,cr2,cr3,want,sz,werr,waddr) \
        check(v,e,proc,addr,selector,stack,seg,err,cr2,cr3,want,sz,werr,waddr)
    assert( VALID(14,14,0,rip,cs,rsp,ss,5,k,p,p,128,5,k));
    assert( VALID(14,14,0,rip,cs,rsp,ss,7,HTMLK_M4_ISO_USER_START,
                  p,p,128,7,HTMLK_M4_ISO_USER_START));
    assert( VALID(13,13,0,rip,cs,rsp,ss,0,0,p,p,128,0,0));
    assert(!VALID(14,14,1,rip,cs,rsp,ss,5,k,p,p,128,5,k)); /* survivor */
    assert(!VALID(14,14,0,rip,8,rsp,ss,5,k,p,p,128,5,k)); /* ring 0 */
    assert(!VALID(14,14,0,rip,cs,rsp,0x10,5,k,p,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,p,p+4096,128,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,p+1,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,0,p,128,5,k));
    assert(!VALID(14,13,0,rip,cs,rsp,ss,5,k,p,p,128,5,k));
    assert(!VALID(13,14,0,rip,cs,rsp,ss,0,0,p,p,128,0,0));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,7,k,p,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k+1,p,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,7,HTMLK_M4_ISO_USER_START,
                  p,p,128,5,k)); /* wrong *configured* fault */
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,p,p,128,7,HTMLK_M4_ISO_USER_START));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,p,p,0,5,k));
    assert(!VALID(14,14,0,rip,cs,rsp,ss,5,k,p,p,4097,5,k));
    assert(!VALID(14,14,0,HTMLK_M4_ISO_USER_START-1,cs,rsp,ss,5,k,p,p,128,5,k));
    assert(!VALID(14,14,0,HTMLK_M4_ISO_USER_START+128,cs,rsp,ss,5,k,p,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,HTMLK_M4_ISO_USER_START+4096,ss,5,k,p,p,128,5,k));
    assert(!VALID(14,14,0,rip,cs,HTMLK_M4_ISO_USER_STACK+8,ss,5,k,p,p,128,5,k));
    assert(!VALID(13,13,0,rip,cs,rsp,ss,1,0,p,p,128,0,0));
    assert(!VALID(13,13,0,rip,cs,rsp,ss,0,1,p,p,128,0,0));
    assert(!VALID(13,13,0,rip,cs,rsp,ss,0,0,p,p,128,5,k));
    puts("M4 C2 FAIL-CLOSED FAULT POLICY UBSAN PASS");
}
