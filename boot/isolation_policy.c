#include "isolation_policy.h"

/* Pure predicate: never "recover" an unexpected CPU fault or kernel fault.
 * The only accepted ring3 crash belongs to task A, at a known address,
 * on precisely its own CR3. Additional fault types fail closed.
 */
bool htmlk_m4_iso_fault_valid(unsigned vector, unsigned intended_vector,
    unsigned process_id, uint64_t rip, uint64_t cs, uint64_t rsp,
    uint64_t ss, uint64_t error, uint64_t cr2,
    uint64_t current_cr3, uint64_t expected_cr3, uint64_t text_bytes,
    uint64_t expected_error, uint64_t expected_cr2) {
    if (process_id != 0U || vector != intended_vector ||
        (vector != 13U && vector != 14U) ||
        cs != HTMLK_M4_ISO_USER_CS ||
        ss != HTMLK_M4_ISO_USER_SS ||
        current_cr3 == 0 || current_cr3 != expected_cr3 ||
        (current_cr3 & ~HTMLK_M4_ISO_CR3_MASK) != 0 ||
        text_bytes == 0 || text_bytes > 4096 ||
        rip < HTMLK_M4_ISO_USER_START ||
        rip - HTMLK_M4_ISO_USER_START >= text_bytes ||
        rsp <= HTMLK_M4_ISO_USER_START + 4096 ||
        rsp > HTMLK_M4_ISO_USER_STACK) return false;
    if (vector == 13U)
        return expected_error == 0U && expected_cr2 == 0U &&
               error == 0U && cr2 == 0U;
    if (!((expected_error == 5U &&
           expected_cr2 == HTMLK_M4_ISO_BAD_KERNEL_ADDRESS) ||
          (expected_error == 7U &&
           expected_cr2 == HTMLK_M4_ISO_USER_START))) return false;
    return error == expected_error && cr2 == expected_cr2;
}
