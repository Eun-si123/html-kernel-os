#ifndef HTMLK_M4_ISOLATION_POLICY_H
#define HTMLK_M4_ISOLATION_POLICY_H
#include <stdbool.h>
#include <stdint.h>
#define HTMLK_M4_ISO_USER_CS UINT64_C(0x2b)
#define HTMLK_M4_ISO_USER_SS UINT64_C(0x33)
#define HTMLK_M4_ISO_BAD_KERNEL_ADDRESS UINT64_C(0xffffffff80001000)
#define HTMLK_M4_ISO_USER_START UINT64_C(0x0000400000000000)
#define HTMLK_M4_ISO_USER_STACK UINT64_C(0x0000400000002000)
#define HTMLK_M4_ISO_CR3_MASK UINT64_C(0x000ffffffffff000)

bool htmlk_m4_iso_fault_valid(unsigned vector, unsigned intended_vector,
    unsigned process_id, uint64_t rip, uint64_t cs, uint64_t rsp,
    uint64_t ss, uint64_t error, uint64_t cr2,
    uint64_t current_cr3, uint64_t expected_cr3, uint64_t text_bytes,
    uint64_t expected_error, uint64_t expected_cr2);
#endif
