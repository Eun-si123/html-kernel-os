/* Portable C11 layout oracle for the actual M3 private-root page-table helper. */
#include "paging_probe.h"
#include <stdint.h>
#include <stdio.h>

#define CHECK(v) do { \
    if (!(v)) { \
        (void)fprintf(stderr, "M3 paging contract line %d: %s\n", __LINE__, #v); \
        return 1; \
    } \
} while (0)

static uint64_t pml4[512], pdpt[512], pd[512], pt[512];
_Static_assert(HTMLK_PAGING_SLOT == 320, "pinned safe demo PML4 index");
_Static_assert(((HTMLK_PAGING_VADDR >> 39) & 511) == HTMLK_PAGING_SLOT,
               "virtual alias must match reserved PML4 index");
_Static_assert(((HTMLK_PAGING_VADDR >> 12) & 0x7ffffff) == 0,
               "alias must use level-3/2/1 entries 0");

int main(void) {
    /* Simulate a bootloader-owned kernel PML4 mapping we must preserve. */
    pml4[511] = UINT64_C(0x00fe0003);
    CHECK(htmlk_paging_wire(pml4, pdpt, pd, pt,
                            0x2000, 0x3000, 0x4000, 0x5000));
    CHECK(pml4[511] == UINT64_C(0x00fe0003));
    CHECK(pml4[HTMLK_PAGING_SLOT] == 0x2003);
    CHECK(pdpt[0] == 0x3003);
    CHECK(pd[0] == 0x4003);
    CHECK(pt[0] == 0x5003);
    CHECK((pt[0] & 4) == 0); /* never user-accessible */
    CHECK((pml4[HTMLK_PAGING_SLOT] & 4) == 0);
    CHECK(pt[1] == 0 && pdpt[511] == 0 && pd[511] == 0);
    for (unsigned i = 0; i < 512; ++i) {
        if (i != 511 && i != HTMLK_PAGING_SLOT) CHECK(pml4[i] == 0);
    }
    /* An occupied slot must never be overwritten by a second call. */
    CHECK(!htmlk_paging_wire(pml4, pdpt, pd, pt,
                             0x6000, 0x7000, 0x8000, 0x9000));
    CHECK(pml4[HTMLK_PAGING_SLOT] == 0x2003);
    CHECK(pdpt[0] == 0x3003 && pd[0] == 0x4003 && pt[0] == 0x5003);

    pml4[HTMLK_PAGING_SLOT] = 0;
    CHECK(!htmlk_paging_wire(0, pdpt, pd, pt, 0x2000,0x3000,0x4000,0x5000));
    CHECK(!htmlk_paging_wire(pml4, pml4, pd, pt, 0x2000,0x3000,0x4000,0x5000));
    CHECK(!htmlk_paging_wire(pml4, pdpt, pd, pt, 0,0x3000,0x4000,0x5000));
    CHECK(!htmlk_paging_wire(pml4, pdpt, pd, pt, 0x2001,0x3000,0x4000,0x5000));
    CHECK(!htmlk_paging_wire(pml4, pdpt, pd, pt, 0x2000,0x2000,0x4000,0x5000));
    CHECK(!htmlk_paging_wire(pml4, pdpt, pd, pt,
                             UINT64_C(0x0010000000000000),0x3000,0x4000,0x5000));
    CHECK(pml4[HTMLK_PAGING_SLOT] == 0);
    CHECK(pml4[511] == UINT64_C(0x00fe0003));
    CHECK(pdpt[0] == 0x3003 && pd[0] == 0x4003 && pt[0] == 0x5003);

    /* A revoked mapping must no longer have a present leaf PTE. */
    CHECK(htmlk_paging_wire(pml4, pdpt, pd, pt,
                            0x6000, 0x7000, 0x8000, 0x9000));
    CHECK(pt[0] == 0x9003);
    pt[0] = 0;
    CHECK(pt[0] == 0 && pml4[511] == UINT64_C(0x00fe0003));
    (void)puts("M3 PRIVATE PAGE TABLE C11 CONTRACT PASS");
    return 0;
}
