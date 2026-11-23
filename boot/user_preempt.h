#ifndef HTMLK_M4_USER_PREEMPT_H
#define HTMLK_M4_USER_PREEMPT_H
#include "limine.h"
#include "preempt_x2apic.h"
#include <stdbool.h>
#include <stdint.h>
struct htmlk_m4_d_irq_frame {
    uint64_t r15,r14,r13,r12,r11,r10,r9,r8;
    uint64_t rbp,rdi,rsi,rdx,rcx,rbx,rax;
    uint64_t rip,cs,rflags,rsp,ss;
};
_Static_assert(sizeof(struct htmlk_m4_d_irq_frame) == 160U,
    "M4-D saved user-context IRQ layout");
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *map,
    const struct limine_hhdm_response *hhdm);
bool htmlk_m4_d_accept_fault(unsigned vec, uint64_t rip, uint64_t cs,
    uint64_t flags, uint64_t rsp, uint64_t ss, uint64_t err, uint64_t cr2);
__attribute__((noreturn)) void htmlk_m4_d_retire_fault(void);
__attribute__((noreturn)) void htmlk_m4_d_user_syscall(struct htmlk_m4_d_irq_frame *frame);
void htmlk_m4_d_syscall_entry(void);
__attribute__((noreturn)) void htmlk_m4_d_return_main(void);
extern const unsigned char htmlk_m4_d_a_begin[], htmlk_m4_d_a_end[];
extern const unsigned char htmlk_m4_d_b_begin[], htmlk_m4_d_b_end[];
#endif
