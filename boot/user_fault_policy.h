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
#endif
