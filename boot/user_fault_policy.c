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

/* Unlike INT80/x2APIC 160-byte frames, CPU #DE/#UD without error codes
 * enters with exactly five 64-bit CPU words: RIP, CS, RFLAGS, RSP, SS.
 * TSS.RSP0 and the original private-user CR3 are supervisor-owned values.
 * This narrow fallback MUST NOT rescue a kernel-origin or unexpected fault. */
/* Strictly two fault-class no-error-code vectors. Other no-error-code
 * exceptions (#DB/#BP) are traps with different saved RIP semantics;
 * error-code exceptions (#GP/#PF) use a different CPU frame size. */
bool htmlk_m5_bad_noerr_fault_vector(unsigned vector) {
    return vector == 0U || vector == 6U;
}

bool htmlk_m5_bad_noerr_stack_owned(const struct htmlk_m5_bad_noerr_owner *c) {
    if (!c || !c->has_active_app || c->already_terminated ||
        c->live_frames != 6U ||
        c->tss_rsp0 < UINT64_C(40) ||
        (c->tss_rsp0 & UINT64_C(15)) != 0 ||
        (c->tss_rsp0 >> 48U) != UINT64_C(0xffff) ||
        (c->tss_rsp0 & (UINT64_C(1) << 47)) == 0 ||
        c->frame_address != c->tss_rsp0 - UINT64_C(40) ||
        c->cs != UINT64_C(0x2b) || c->ss != UINT64_C(0x33) ||
        (c->rflags & UINT64_C(2)) == 0 ||
        (((c->rflags >> 9U) & UINT64_C(1)) != (uint64_t)c->expected_if) ||
        (c->rflags & (UINT64_C(3) << 12 | UINT64_C(1) << 14 |
                      UINT64_C(1) << 17)) != 0 ||
        c->code_bytes == 0 || c->code_bytes > HTMLK_HKE_MAX_CODE_BYTES ||
        c->rip < HTMLK_M4_USER_BASE ||
        c->rip - HTMLK_M4_USER_BASE >= c->code_bytes ||
        c->owned_cr3 == 0 || (c->owned_cr3 & UINT64_C(4095)) != 0 ||
        c->active_cr3 != c->owned_cr3 ||
        c->saved_cr3 == 0 || c->saved_cr3 == c->owned_cr3 ||
        c->saved_main_rsp == 0 ||
        (c->saved_main_rsp >> 48U) != UINT64_C(0xffff) ||
        (c->saved_main_rsp & (UINT64_C(1) << 47)) == 0)
        return false;
    /* Only an actually bad user stack can use this exception-specific
     * fallback. Valid-stack CPU exceptions still use the strict policy. */
    return c->user_rsp <= HTMLK_M4_USER_BASE + UINT64_C(4096) ||
           c->user_rsp > HTMLK_M4_USER_STACK;
}
