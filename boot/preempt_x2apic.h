#ifndef HTMLK_M4_PREEMPT_X2APIC_H
#define HTMLK_M4_PREEMPT_X2APIC_H
#include <stdint.h>

/* Dedicated x2APIC opt-in, single CPU, kernel-only preemption proof. */
#define HTMLK_M4_PREEMPT_VECTOR 0x40U
#define HTMLK_M4_TASK_COUNT 2U
#define HTMLK_M4_STEPS 3U

/* Assembly entry/exit frame: 15 saved GPRs, architectural iret frame. */
struct htmlk_m4_irq_frame {
    uint64_t r15, r14, r13, r12, r11, r10, r9, r8;
    uint64_t rbp, rdi, rsi, rdx, rcx, rbx, rax;
    uint64_t rip, cs, rflags, rsp, ss;
};
_Static_assert(sizeof(struct htmlk_m4_irq_frame) == 20U * sizeof(uint64_t),
               "M4: IRQ frame layout mismatch");

extern uint64_t *htmlk_m4_main_stack;
void htmlk_m4_preempt_probe(void);
void htmlk_m4_x2apic_irq_entry(void);
void htmlk_m4_x2apic_spurious_entry(void);
void htmlk_m4_enter_first(uint64_t *stack);
uint64_t *htmlk_m4_on_timer_irq(uint64_t *irq_stack);
#endif
