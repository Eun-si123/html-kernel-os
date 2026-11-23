#include "user_pages.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>

int main(void) {
    uint64_t root[512] = {0}, pdpt[512] = {0};
    uint64_t pd[512] = {0}, pt[512] = {0};
    const uint64_t phys[6] = {0x1000,0x2000,0x3000,0x4000,0x5000,0x6000};
    uint64_t invalid[6] = {0x1000,0x2000,0x3000,0x4000,0x5000,0x6000};
    assert(!htmlk_m4_user_wire(0,pdpt,pd,pt,phys));
    assert(!htmlk_m4_user_wire(root,root,pd,pt,phys));
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,0));
    invalid[4] = invalid[5];
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,invalid));
    invalid[4] = 0x5001;
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,invalid));
    invalid[4] = 0;
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,invalid));
    invalid[4] = UINT64_C(0x10000000000000);
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,invalid));
    root[HTMLK_M4_USER_SLOT] = 0x1234;
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,phys));
    root[HTMLK_M4_USER_SLOT] = 0;
    root[1] = UINT64_C(0x12345003); /* inherited kernel root is not altered */
    assert(htmlk_m4_user_wire(root,pdpt,pd,pt,phys));
    assert(root[1] == UINT64_C(0x12345003));
    assert((root[HTMLK_M4_USER_SLOT] & 7U) == 7U);
    assert((pdpt[0] & 7U) == 7U);
    assert((pd[0] & 7U) == 7U);
    assert((pt[0] & 7U) == 5U); /* user read/execute, not write */
    assert((pt[1] & 7U) == 7U); /* user stack read/write */
    assert((pt[0] & HTMLK_M4_USER_PHYS_MASK) == phys[4]);
    assert((pt[1] & HTMLK_M4_USER_PHYS_MASK) == phys[5]);
    for(unsigned i = 2; i < 512; ++i) assert(pt[i] == 0);
    assert(!htmlk_m4_user_wire(root,pdpt,pd,pt,phys));
    puts("M4 RING3 PAGES PERMISSIONS + NEGATIVE REJECTION PASS");
}
