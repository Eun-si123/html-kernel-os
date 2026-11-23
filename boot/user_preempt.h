#ifndef HTMLK_M4_USER_PREEMPT_H
#define HTMLK_M4_USER_PREEMPT_H
#include "limine.h"
#include "preempt_x2apic.h"
#include <stdbool.h>
#include <stdint.h>
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *,
                                 const struct limine_hhdm_response *);
uint64_t *htmlk_m4_d_timer_handler(uint64_t *frame);
bool htmlk_m4_d_accept_fault(uint64_t rip, uint64_t cs, uint64_t rsp,
                              uint64_t ss, uint64_t error, uint64_t cr2);
__attribute__((noreturn)) void htmlk_m4_d_recover_fault(void);
void htmlk_m4_d_timer_entry(void);
void htmlk_m4_d_spurious_entry(void);
void htmlk_m4_d_enter_first(uint64_t *frame);
__attribute__((noreturn)) void htmlk_m4_d_resume_user(uint64_t *frame);
extern const unsigned char htmlk_m4_d_bad_begin[], htmlk_m4_d_bad_end[];
extern const unsigned char htmlk_m4_d_good_begin[], htmlk_m4_d_good_end[];
#endif
