#ifndef HTMLK_M5_USER_SYSCALL_POLICY_H
#define HTMLK_M5_USER_SYSCALL_POLICY_H
#include <stdint.h>
#include <stdbool.h>

/* Independent host-testable ownership proof before aborting a malformed
 * CPL3 INT80 frame. RIP and RSP are deliberately NOT trusted for this proof:
 * a corrupted userspace stack pointer is the scenario to contain. */
struct htmlk_m5_syscall_provenance {
    uint64_t frame_address; /* actual pushed 15 GPR + 5-word hardware frame */
    uint64_t tss_rsp0;      /* trusted ring0 interrupt stack top */
    uint64_t cs,ss,rflags;
    uint64_t active_cr3,owned_cr3,saved_cr3,saved_main_rsp;
    unsigned live_frames;
    bool has_active_app;
    bool already_terminated;
};
bool htmlk_m5_bad_syscall_frame_is_owned(
    const struct htmlk_m5_syscall_provenance *context);
#endif
