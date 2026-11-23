/* Freestanding and host-testable 4KiB x86-64 supervisor-only page-table helper. */
#include "paging_probe.h"

bool htmlk_paging_wire(volatile uint64_t *root,
                       volatile uint64_t *pdpt,
                       volatile uint64_t *pd,
                       volatile uint64_t *pt,
                       uint64_t pdpt_phys, uint64_t pd_phys,
                       uint64_t pt_phys, uint64_t page_phys) {
    if (root == 0 || pdpt == 0 || pd == 0 || pt == 0 ||
        root == pdpt || root == pd || root == pt ||
        pdpt == pd || pdpt == pt || pd == pt) {
        return false;
    }
    const uint64_t frames[4] = { pdpt_phys, pd_phys, pt_phys, page_phys };
    for (unsigned i = 0; i < 4; ++i) {
        if (frames[i] == 0 ||
            (frames[i] & ~HTMLK_PAGING_PHYS_MASK) != 0) {
            return false;
        }
        for (unsigned j = i + 1; j < 4; ++j) {
            if (frames[i] == frames[j]) return false;
        }
    }
    /* Do not clobber an existing Limine HHDM, kernel, or future mapping. */
    if (root[HTMLK_PAGING_SLOT] != 0) return false;
    for (unsigned i = 0; i < 512; ++i) {
        pdpt[i] = 0;
        pd[i] = 0;
        pt[i] = 0;
    }
    pdpt[0] = pd_phys | HTMLK_PAGING_ENTRY_RW;
    pd[0] = pt_phys | HTMLK_PAGING_ENTRY_RW;
    pt[0] = page_phys | HTMLK_PAGING_ENTRY_RW;
    root[HTMLK_PAGING_SLOT] = pdpt_phys | HTMLK_PAGING_ENTRY_RW;
    return true;
}

