#ifndef HTMLK_M4_USER_PAGES_H
#define HTMLK_M4_USER_PAGES_H
#include <stdbool.h>
#include <stdint.h>
#define HTMLK_M4_USER_BASE UINT64_C(0x0000400000000000)
#define HTMLK_M4_USER_STACK (HTMLK_M4_USER_BASE + UINT64_C(0x2000))
#define HTMLK_M4_USER_SLOT 128U
#define HTMLK_M4_USER_PRESENT UINT64_C(1)
#define HTMLK_M4_USER_WRITE UINT64_C(2)
#define HTMLK_M4_USER_BIT UINT64_C(4)
#define HTMLK_M4_USER_NX (UINT64_C(1) << 63)
#define HTMLK_M4_USER_PHYS_MASK UINT64_C(0x000ffffffffff000)

bool htmlk_m4_user_wire(volatile uint64_t *root, volatile uint64_t *pdpt,
                        volatile uint64_t *pd, volatile uint64_t *pt,
                        const uint64_t physical[6]);
#endif
