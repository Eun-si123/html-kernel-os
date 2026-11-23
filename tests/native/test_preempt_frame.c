#include "preempt_x2apic.h"
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    assert(sizeof(struct htmlk_m4_irq_frame) == 160U);
    assert(offsetof(struct htmlk_m4_irq_frame, r15) == 0U);
    assert(offsetof(struct htmlk_m4_irq_frame, r11) == 32U);
    assert(offsetof(struct htmlk_m4_irq_frame, rbp) == 64U);
    assert(offsetof(struct htmlk_m4_irq_frame, rax) == 112U);
    assert(offsetof(struct htmlk_m4_irq_frame, rip) == 120U);
    assert(offsetof(struct htmlk_m4_irq_frame, cs) == 128U);
    assert(offsetof(struct htmlk_m4_irq_frame, rflags) == 136U);
    assert(offsetof(struct htmlk_m4_irq_frame, rsp) == 144U);
    assert(offsetof(struct htmlk_m4_irq_frame, ss) == 152U);
    assert(HTMLK_M4_PREEMPT_VECTOR >= 32U);
    assert(HTMLK_M4_TASK_COUNT == 2U);
    puts("M4 X2APIC FULL IRQ FRAME LAYOUT PASS");
}
