#ifndef HTMLK_M4_D_POLICY_H
#define HTMLK_M4_D_POLICY_H
#include <stdbool.h>
#include <stdint.h>
#include "user_pages.h"
#define HTMLK_M4_D_USER_CS UINT64_C(0x2b)
#define HTMLK_M4_D_USER_SS UINT64_C(0x33)
#define HTMLK_M4_D_BAD_ADDRESS UINT64_C(0xffffffff80001000)
bool htmlk_m4_d_user_frame_valid(uint64_t rip, uint64_t cs, uint64_t flags,
    uint64_t rsp, uint64_t ss, uint64_t cr3, uint64_t root,
    uint64_t image_length);
bool htmlk_m4_d_fault_valid(unsigned task, unsigned vector, uint64_t error,
    uint64_t cr2, uint64_t rip, uint64_t cs, uint64_t flags,
    uint64_t rsp, uint64_t ss, uint64_t cr3, uint64_t root,
    uint64_t image_length, unsigned a_steps, unsigned b_steps);
#endif
