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


/* This helper is deliberately limited to a caller-owned 512-entry leaf PT.
 * It does not alter parent page tables, control TLBs, or confer ownership.
 * It rejects duplicate physical frames to avoid alias/double-free confusion.
 */
static bool valid_phys(uint64_t phys) {
    return phys != 0 && (phys & ~HTMLK_PAGING_PHYS_MASK) == 0;
}

bool htmlk_paging_leaf_map(volatile uint64_t *pt,
                           unsigned index, uint64_t phys) {
    if (pt == 0 || index >= 512 || !valid_phys(phys) ||
        pt[index] != 0) return false;
    for (unsigned i = 0; i < 512; ++i) {
        if ((pt[i] & UINT64_C(1)) != 0 &&
            (pt[i] & HTMLK_PAGING_PHYS_MASK) == phys)
            return false;
    }
    pt[index] = phys | HTMLK_PAGING_ENTRY_RW; /* kernel RW, not ring3 */
    return true;
}

bool htmlk_paging_leaf_unmap(volatile uint64_t *pt,
                             unsigned index, uint64_t expected_phys) {
    if (pt == 0 || index >= 512 || !valid_phys(expected_phys) ||
        (pt[index] & UINT64_C(1)) == 0 ||
        (pt[index] & HTMLK_PAGING_PHYS_MASK) != expected_phys)
        return false;
    pt[index] = 0;
    return true;
}
