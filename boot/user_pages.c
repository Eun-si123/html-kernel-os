#include "user_pages.h"
/* Pure mapping helper. root is a private PML4 copy, never Limine's active one. */
bool htmlk_m4_user_wire(volatile uint64_t *root, volatile uint64_t *pdpt,
                        volatile uint64_t *pd, volatile uint64_t *pt,
                        const uint64_t phys[6]) {
    if (!root || !pdpt || !pd || !pt || !phys ||
        root == pdpt || root == pd || root == pt ||
        pdpt == pd || pdpt == pt || pd == pt ||
        root[HTMLK_M4_USER_SLOT] != 0) return false;
    for (unsigned i = 0; i < 6; ++i) {
        if (phys[i] == 0 || (phys[i] & ~HTMLK_M4_USER_PHYS_MASK) != 0)
            return false;
        for (unsigned j = i + 1; j < 6; ++j)
            if (phys[i] == phys[j]) return false;
    }
    for (unsigned i = 0; i < 512; ++i) {
        pdpt[i] = 0;
        pd[i] = 0;
        pt[i] = 0;
    }
    const uint64_t rw_user =
        HTMLK_M4_USER_PRESENT | HTMLK_M4_USER_WRITE | HTMLK_M4_USER_BIT;
    pdpt[0] = phys[2] | rw_user;
    pd[0] = phys[3] | rw_user;
    pt[0] = phys[4] | HTMLK_M4_USER_PRESENT | HTMLK_M4_USER_BIT; /* code RO */
    pt[1] = phys[5] | rw_user; /* stack RW, user */
    root[HTMLK_M4_USER_SLOT] = phys[1] | rw_user;
    return true;
}
