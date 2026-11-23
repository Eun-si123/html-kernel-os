#include "user_fault_policy.h"
#include "user_pages.h"
#include "user_image.h"

bool htmlk_m5_user_fault_frame_valid(unsigned vector, uint64_t rip,
                                    uint64_t cs, uint64_t flags,
                                    uint64_t rsp, uint64_t ss,
                                    uint64_t error, uint64_t current_cr3,
                                    uint64_t user_cr3, uint64_t code_bytes) {
    /* A legitimate CPU exception from CPL3 requires a five-word IRET frame.
     * Never evaluate the RSP/SS fields of a CPL0 interrupt frame. */
    if (cs != UINT64_C(0x2b) || ss != UINT64_C(0x33) ||
        code_bytes == 0 || code_bytes > HTMLK_HKE_MAX_CODE_BYTES ||
        rip < HTMLK_M4_USER_BASE ||
        /* #DB/#BP are trap-class exceptions: saved RIP points *after*
         * ICEBP/INT3, possibly one-past-the-last code byte. #DE and
         * other fault-class vectors must refer to an executed code byte. */
        ((vector == 1U || vector == 3U)
         ? rip - HTMLK_M4_USER_BASE > code_bytes
         : rip - HTMLK_M4_USER_BASE >= code_bytes) ||
        rsp <= HTMLK_M4_USER_BASE + 4096U ||
        rsp > HTMLK_M4_USER_STACK ||
        (flags & UINT64_C(0x2)) == 0 ||
        (flags & (UINT64_C(3)<<12 | UINT64_C(1)<<14 |
                  UINT64_C(1)<<17)) != 0 ||
        user_cr3 == 0 || (user_cr3 & UINT64_C(4095)) != 0 ||
        current_cr3 != user_cr3) return false;
    if (vector == 0U || vector == 1U || vector == 3U ||
        vector == 6U || vector == 13U)
        return error == 0;
    if (vector == 14U)
        return (error & 4U) != 0U && (error & ~UINT64_C(0x7f)) == 0;
    return false;
}
