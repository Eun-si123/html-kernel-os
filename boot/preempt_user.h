#ifndef HTMLK_M4_D_USER_PREEMPT_H
#define HTMLK_M4_D_USER_PREEMPT_H
#include <stdbool.h>
#include <stdint.h>
#define HTMLK_M4_D_TIMER_VECTOR 0x40U
#define HTMLK_M4_D_TASKS 2U
#define HTMLK_M4_D_A_RBX UINT64_C(0x1122334455667788)
#define HTMLK_M4_D_B_RBX UINT64_C(0x8877665544332211)
#define HTMLK_M4_D_A_R12 UINT64_C(0x99aabbccddeeff00)
#define HTMLK_M4_D_B_R12 UINT64_C(0x00ffeeddccbbaa99)
#define HTMLK_M4_D_A_R10 UINT64_C(0x0102030405060708)
#define HTMLK_M4_D_B_R10 UINT64_C(0x0807060504030201)
struct limine_memmap_response;
struct limine_hhdm_response;
struct htmlk_m4_d_frame {
    uint64_t r15,r14,r13,r12,r11,r10,r9,r8;
    uint64_t rbp,rdi,rsi,rdx,rcx,rbx,rax;
    uint64_t rip,cs,rflags,rsp,ss;
};
bool htmlk_m4_d_arch_frame_valid(const struct htmlk_m4_d_frame *f,
                                 unsigned task, uint64_t bytes);
_Static_assert(sizeof(struct htmlk_m4_d_frame) == 160,
               "full CPL3 IRQ frame must include hardware SS/RSP");
void htmlk_m4_d_probe(const struct limine_memmap_response *map,
                      const struct limine_hhdm_response *hhdm);
void htmlk_m4_d_timer_entry(void);
void htmlk_m4_d_spurious_entry(void);
void htmlk_m4_d_enter(uint64_t *irq_stack);
__attribute__((noreturn)) void htmlk_m4_d_resume(uint64_t *irq_stack);
uint64_t *htmlk_m4_d_on_timer(struct htmlk_m4_d_frame *frame);
bool htmlk_m4_d_accept_fault(unsigned vector, uint64_t rip, uint64_t cs,
                            uint64_t rsp, uint64_t ss, uint64_t error,
                            uint64_t cr2);
extern uint64_t *htmlk_m4_d_main_rsp;
extern const unsigned char htmlk_m4_d_bad_begin[], htmlk_m4_d_bad_end[];
extern const unsigned char htmlk_m4_d_good_begin[], htmlk_m4_d_good_end[];
#endif
