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
    assert(GOOD(6U,0)); assert(GOOD(13U,0));
    assert(GOOD(14U,4)); assert(GOOD(14U,5));
    assert(GOOD(14U,6)); assert(GOOD(14U,7));
    assert(!GOOD(14U,0)); assert(!GOOD(14U,1));
    assert(!GOOD(14U,0x84)); assert(!GOOD(13U,1));
    assert(!GOOD(6U,4)); assert(!GOOD(0U,0)); assert(!GOOD(8U,0));
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
    puts("M5-E1 USER EXCEPTION FRAME/CR3/SEL/ERR GUARDS PASS");
}
