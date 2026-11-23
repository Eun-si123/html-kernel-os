#ifndef HTMLK_M4_USER_PREEMPT_H
#define HTMLK_M4_USER_PREEMPT_H
#include "limine.h"
#include "user_preempt_frame.h"
#include <stdint.h>

/* M4-D1 single-vCPU, test-only preemptive CPL3 execution. */
enum { HTMLK_M4_D1_COUNT = 2, HTMLK_M4_D1_FRAMES = 6 };
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *map,
                                 const struct limine_hhdm_response *hhdm);
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_on_irq(
    struct htmlk_m4_d1_irq_frame *f);
void htmlk_m4_d1_irq_entry(void);
void htmlk_m4_d1_spurious(void);
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_page_fault(
    uint64_t rip, uint64_t cs, uint64_t rsp, uint64_t ss,
    uint64_t error, uint64_t cr2);
__attribute__((noreturn))
void htmlk_m4_d1_switch_from_fault(struct htmlk_m4_d1_irq_frame *next);
void htmlk_m4_d1_start(struct htmlk_m4_d1_irq_frame *initial);
extern uint64_t *htmlk_m4_d1_main_rsp;
extern const unsigned char htmlk_m4_d1_a_begin[], htmlk_m4_d1_a_end[];
extern const unsigned char htmlk_m4_d1_b_begin[], htmlk_m4_d1_b_end[];
extern const unsigned char htmlk_m4_d1_a_loop[], htmlk_m4_d1_b_loop[];
#ifdef HTMLK_M4_D2_FAULT
extern const unsigned char htmlk_m4_d1_a_fault[];
#endif
#endif
