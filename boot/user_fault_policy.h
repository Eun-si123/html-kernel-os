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
#endif
