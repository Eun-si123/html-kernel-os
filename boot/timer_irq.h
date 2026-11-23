#ifndef HTMLK_M4_TIMER_IRQ_H
#define HTMLK_M4_TIMER_IRQ_H
#include <stdint.h>
/* QEMU legacy PIT IRQ0 probe; no preemptive scheduler/real-hardware guarantee. */
uint16_t htmlk_m4_pit_divisor(unsigned hz);
void htmlk_m4_timer_init(void);
void htmlk_m4_timer_wait(void);
void htmlk_m4_timer_finish(void);
void htmlk_m4_irq0_handler(void);
struct m4_interrupt_frame;
__attribute__((interrupt)) void htmlk_m4_irq0_entry(struct m4_interrupt_frame *frame);
#endif
