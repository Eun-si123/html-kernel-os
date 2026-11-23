#ifndef HTMLK_M4_USER_PROBE_H
#define HTMLK_M4_USER_PROBE_H
#include "limine.h"
#include <stdint.h>

void htmlk_m4_user_probe(const struct limine_memmap_response *map,
                         const struct limine_hhdm_response *hhdm);
void htmlk_m4_syscall_entry(void);
void htmlk_m4_syscall_dispatch(void *frame);
void htmlk_m4_user_enter(uint64_t rip, uint64_t rsp, uint64_t cs, uint64_t ss);
__attribute__((noreturn)) void htmlk_m4_user_return(void);
extern uint64_t *htmlk_m4_saved_main_rsp;
extern uint64_t htmlk_m4_saved_cr3;
extern const unsigned char htmlk_m4_user_code_begin[];
extern const unsigned char htmlk_m4_user_code_end[];
#endif
