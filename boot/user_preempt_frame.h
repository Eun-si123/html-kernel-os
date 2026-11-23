#ifndef HTMLK_M4_USER_PREEMPT_FRAME_H
#define HTMLK_M4_USER_PREEMPT_FRAME_H
#include <stdbool.h>
#include <stdint.h>
/* Saved IRQ stack begins with 15 GPRs and a genuine CPL3 5-word IRET frame. */
struct htmlk_m4_d1_irq_frame {
    uint64_t r15, r14, r13, r12, r11, r10, r9, r8;
    uint64_t rbp, rdi, rsi, rdx, rcx, rbx, rax;
    uint64_t rip, cs, rflags, rsp, ss;
};
_Static_assert(sizeof(struct htmlk_m4_d1_irq_frame) == 160U,
               "M4-D ring3 IRQ frame layout");
bool htmlk_m4_d1_frame_guard(const struct htmlk_m4_d1_irq_frame *frame,
                            uintptr_t bottom, uintptr_t top,
                            uint64_t code_len, uint64_t loop_offset,
                            uint64_t rbx, uint64_t r12);
#endif
