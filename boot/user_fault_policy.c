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

/* Shared strict provenance. Frame size/layout is checked separately by each
 * vector-specific wrapper; never turn this helper into a generic fault pass. */
static bool cpu_owner_valid(const struct htmlk_m5_bad_noerr_owner *c) {
    if (!c || !c->has_active_app || c->already_terminated ||
        c->live_frames != 6U ||
        c->tss_rsp0 < UINT64_C(48) ||
        (c->tss_rsp0 & UINT64_C(15)) != 0 ||
        (c->tss_rsp0 >> 48U) != UINT64_C(0xffff) ||
        (c->tss_rsp0 & (UINT64_C(1) << 47)) == 0 ||
        c->cs != UINT64_C(0x2b) || c->ss != UINT64_C(0x33) ||
        (c->rflags & UINT64_C(2)) == 0 ||
        (((c->rflags >> 9U) & UINT64_C(1)) != (uint64_t)c->expected_if) ||
        (c->rflags & (UINT64_C(3) << 12 | UINT64_C(1) << 14 |
                      UINT64_C(1) << 17)) != 0 ||
        c->code_bytes == 0 || c->code_bytes > HTMLK_HKE_MAX_CODE_BYTES ||
        c->owned_cr3 == 0 || (c->owned_cr3 & UINT64_C(4095)) != 0 ||
        c->active_cr3 != c->owned_cr3 ||
        c->saved_cr3 == 0 || c->saved_cr3 == c->owned_cr3 ||
        c->saved_main_rsp == 0 ||
        (c->saved_main_rsp >> 48U) != UINT64_C(0xffff) ||
        (c->saved_main_rsp & (UINT64_C(1) << 47)) == 0)
        return false;
    return true;
}

static bool bad_rsp_owner_valid(const struct htmlk_m5_bad_noerr_owner *c) {
    if (!cpu_owner_valid(c) || c->rip < HTMLK_M4_USER_BASE ||
        c->rip - HTMLK_M4_USER_BASE >= c->code_bytes) return false;
    /* Only an actually bad user stack can use this exception-specific
     * fallback. Valid-stack CPU exceptions still use the strict policy. */
    return c->user_rsp <= HTMLK_M4_USER_BASE + UINT64_C(4096) ||
           c->user_rsp > HTMLK_M4_USER_STACK;
}

/* The original no-error-code proof still only accepts the exact five-word
 * frame and never enables #GP by itself. */
bool htmlk_m5_bad_noerr_stack_owned(const struct htmlk_m5_bad_noerr_owner *c) {
    return c && c->frame_address == c->tss_rsp0 - UINT64_C(40) &&
           bad_rsp_owner_valid(c);
}

/* Trap-class #DB/#BP save RIP *after* the trap opcode, including the
 * exact one-past-end byte. Preserve all original strict owner checks and
 * special-case only the trusted CPU trap RIP bound in a local copy.
 * Fault-class #DE/#UD, #GP and #PF continue to reject code-end RIP. */
bool htmlk_m5_bad_trap_stack_owned(unsigned vector,
                                   const struct htmlk_m5_bad_noerr_owner *ctx) {
    if ((vector != 1U && vector != 3U) || !ctx ||
        ctx->frame_address != ctx->tss_rsp0 - UINT64_C(40) ||
        ctx->rip <= HTMLK_M4_USER_BASE)
        return false;
    struct htmlk_m5_bad_noerr_owner owner = *ctx;
    if (owner.code_bytes != 0 && owner.code_bytes <= HTMLK_HKE_MAX_CODE_BYTES &&
        owner.rip - HTMLK_M4_USER_BASE == owner.code_bytes) {
        owner.rip -= 1U; /* validate previous instruction within bound */
    }
    return bad_rsp_owner_valid(&owner);
}

/* CPU #GP pushes an extra 8-byte error word BEFORE five IRET words.
 * GCC passes f pointing at the first IRET word (RIP), NOT the error code.
 * Require both exact words relative to the *trusted* TSS.RSP0, plus
 * CPU error code 0 (general protection from user privileged I/O). */
bool htmlk_m5_bad_gp_stack_owned(const struct htmlk_m5_bad_gp_owner *ctx) {
    if (!ctx || ctx->frame.tss_rsp0 < UINT64_C(48) ||
        ctx->error_code != 0U ||
        ctx->error_word_address != ctx->frame.tss_rsp0 - UINT64_C(48) ||
        ctx->frame.frame_address != ctx->frame.tss_rsp0 - UINT64_C(40) ||
        ctx->error_word_address != ctx->frame.frame_address - UINT64_C(8))
        return false;
    return bad_rsp_owner_valid(&ctx->frame);
}

/* Only scoped user-origin #PF: present-page 5/7 or nonpresent guard 4/6.
 * A kernel fault or a fault delivered to some other stack can never use
 * this emergency user-process retirement. */
static bool pf_frame_owned(const struct htmlk_m5_bad_pf_owner *ctx) {
    if (!ctx || ctx->ist2_top == 0 ||
        ctx->frame.tss_rsp0 != ctx->ist2_top ||
        ctx->frame.tss_rsp0 < UINT64_C(48) ||
        ctx->error_word_address != ctx->ist2_top - UINT64_C(48) ||
        ctx->frame.frame_address != ctx->ist2_top - UINT64_C(40) ||
        ctx->error_word_address != ctx->frame.frame_address - UINT64_C(8))
        return false;
    return cpu_owner_valid(&ctx->frame);
}

bool htmlk_m5_bad_pf_stack_owned(const struct htmlk_m5_bad_pf_owner *ctx) {
    if (!pf_frame_owned(ctx)) return false;
    if (ctx->error_code == 5U) {
        /* Read access from CPL3 to a privileged canonical high address. */
        if (ctx->cr2 < UINT64_C(0xffff800000000000)) return false;
    } else if (ctx->error_code == 7U) {
        /* CPL3 attempted to write its private mapped RX user code page. */
        if (ctx->cr2 < HTMLK_M4_USER_BASE ||
            ctx->cr2 - HTMLK_M4_USER_BASE >= UINT64_C(4096)) return false;
    } else if (ctx->error_code == 4U || ctx->error_code == 6U) {
        /* Nonpresent user data access only to the immediately adjacent
         * unmapped guard page. The private page table wires only entries
         * 0 (code) and 1 (stack); no mapping or fault fixup is performed. */
        if (ctx->cr2 < HTMLK_M4_USER_STACK ||
            ctx->cr2 - HTMLK_M4_USER_STACK >= UINT64_C(4096)) return false;
    } else {
        return false;
    }
    return bad_rsp_owner_valid(&ctx->frame);
}

/* Exact present/user/instruction-fetch protection error (P|U|I).
 * Unlike data faults, saved RIP is the attempted stack instruction;
 * never pretend it is a valid executable RIP or retry it. */
bool htmlk_m5_nx_stack_fault_owned(const struct htmlk_m5_bad_pf_owner *ctx) {
    return pf_frame_owned(ctx) && ctx->error_code == 21U &&
           ctx->frame.rip == ctx->cr2 &&
           ctx->cr2 >= HTMLK_M4_USER_BASE + UINT64_C(4096) &&
           ctx->cr2 < HTMLK_M4_USER_STACK;
}
