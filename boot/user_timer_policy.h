#ifndef HTMLK_USER_TIMER_POLICY_H
#define HTMLK_USER_TIMER_POLICY_H
#include "preempt_x2apic.h"
#include <stdbool.h>
#include <stdint.h>
/* Pure AMD64 frame/stack ownership check, shared by host and guest tests.
 * The CPU iret frame is ALWAYS 5 words for CPL3, unlike a CPL0 IRQ.
 */
bool htmlk_m4_d_frame_valid(const struct htmlk_m4_irq_frame *frame,
                           uintptr_t stack_start, uint64_t stack_size,
                           uint64_t user_code_size);
#endif
