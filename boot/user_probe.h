#ifndef HTMLK_M4_USER_PROBE_H
#define HTMLK_M4_USER_PROBE_H
#include "limine.h"
#include <stdint.h>
#include <stdbool.h>

void htmlk_m4_user_probe(const struct limine_memmap_response *map,
                         const struct limine_hhdm_response *hhdm);
#ifdef HTMLK_M5_INTERACTIVE_RUN
void htmlk_m5_user_run(const char *path,
                       const struct limine_memmap_response *map,
                       const struct limine_hhdm_response *hhdm);
void htmlk_m5_console_byte(uint8_t byte);
#ifdef HTMLK_M5_USER_FAULT_RECOVER
bool htmlk_m5_user_last_faulted(void);
bool htmlk_m5_user_last_bad_syscall(void);
#ifdef HTMLK_M5_USER_EXIT_STATUS
uint8_t htmlk_m5_user_last_exit_status(void);
#endif
#ifdef HTMLK_M5_USER_TIMEOUT
struct htmlk_m4_d1_irq_frame;
bool htmlk_m5_user_last_timed_out(void);
bool htmlk_m5_timeout_irq_context_valid(const struct htmlk_m4_d1_irq_frame *frame);
__attribute__((noreturn)) void htmlk_m5_timeout_expire(void);
#endif
bool htmlk_m5_accept_user_fault(unsigned vector, uint64_t rip,
                                uint64_t cs, uint64_t flags,
                                uint64_t rsp, uint64_t ss,
                                uint64_t error, uint64_t cr2);
#endif
#endif
void htmlk_m4_syscall_entry(void);
void htmlk_m4_syscall_dispatch(void *frame);
void htmlk_m4_user_enter(uint64_t rip, uint64_t rsp, uint64_t cs, uint64_t ss);
__attribute__((noreturn)) void htmlk_m4_user_return(void);
extern uint64_t *htmlk_m4_saved_main_rsp;
extern uint64_t htmlk_m4_saved_cr3;
extern const unsigned char htmlk_m4_user_code_begin[];
extern const unsigned char htmlk_m4_user_code_end[];
#endif
