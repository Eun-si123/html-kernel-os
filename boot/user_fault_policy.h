#ifndef HTMLK_M5_USER_FAULT_POLICY_H
#define HTMLK_M5_USER_FAULT_POLICY_H
#include <stdbool.h>
#include <stdint.h>

/* Pure validation; caller must additionally prove an active, owned process. */
bool htmlk_m5_user_fault_frame_valid(unsigned vector, uint64_t rip,
                                    uint64_t cs, uint64_t flags,
                                    uint64_t rsp, uint64_t ss,
                                    uint64_t error, uint64_t current_cr3,
                                    uint64_t user_cr3, uint64_t code_bytes);
/* Independently prove 5-word CPL3 #DE/#UD CPU frame on trusted TSS.RSP0.
 * Only a known live task with a BAD *user* RSP may be retired. No user
 * address is ever dereferenced; kernel/unowned/forged-origin faults fail. */
struct htmlk_m5_bad_noerr_owner {
    uint64_t frame_address, tss_rsp0, rip, cs, ss, rflags, user_rsp;
    uint64_t active_cr3, owned_cr3, saved_cr3, saved_main_rsp;
    uint64_t code_bytes;
    unsigned live_frames;
    bool has_active_app, already_terminated, expected_if;
};
bool htmlk_m5_bad_noerr_fault_vector(unsigned vector);
bool htmlk_m5_bad_noerr_stack_owned(const struct htmlk_m5_bad_noerr_owner *ctx);
/* Only genuine trap-class no-error-code #DB/#BP with the correct
 * 40-byte TSS.RSP0 frame; CPU-saved RIP may be ONE past code end. */
bool htmlk_m5_bad_trap_stack_owned(unsigned vector,
                                   const struct htmlk_m5_bad_noerr_owner *ctx);
/* x86 #GP pushes an error word at RSP0-48; the five-word IRET frame
 * starts at RSP0-40 (as given to GCC's interrupt function). Never use
 * this separate error-code proof for #PF/IST2 or other exception vectors. */
struct htmlk_m5_bad_gp_owner {
    struct htmlk_m5_bad_noerr_owner frame;
    uint64_t error_word_address, error_code;
};
bool htmlk_m5_bad_gp_stack_owned(const struct htmlk_m5_bad_gp_owner *ctx);
/* #PF is delivered to independently selected TSS.IST2, never RSP0.
 * Error word is 8 bytes below the five-qword CPU frame. The policy
 * proves IST2 ownership, active user CR3 and CR2 + CPU U/S fault bits. */
struct htmlk_m5_bad_pf_owner {
    struct htmlk_m5_bad_noerr_owner frame; /* tss_rsp0 field = trusted IST2 top */
    uint64_t ist2_top, error_word_address, error_code, cr2;
};
bool htmlk_m5_bad_pf_stack_owned(const struct htmlk_m5_bad_pf_owner *ctx);
#endif
