#ifndef HTMLK_M5_USER_TIMEOUT_FRAME_H
#define HTMLK_M5_USER_TIMEOUT_FRAME_H
#include "user_preempt_frame.h"
#include <stdbool.h>
#include <stdint.h>

/* M5-E2 uses the exact 160-byte CPL3 interrupt ABI from M4-D.
 * Dedicated one-process RSP0 stack; no generic switching/scheduler claim. */
bool htmlk_m5_timeout_frame_valid(const struct htmlk_m4_d1_irq_frame *frame,
                                   uint64_t rsp0, uint64_t code_length,
                                   uint64_t current_cr3, uint64_t user_cr3);
#endif
