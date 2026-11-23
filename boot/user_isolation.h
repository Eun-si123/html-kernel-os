#ifndef HTMLK_M4_USER_ISOLATION_H
#define HTMLK_M4_USER_ISOLATION_H
#include "limine.h"
#include <stdbool.h>
#include <stdint.h>

void htmlk_m4_user_isolation_probe(const struct limine_memmap_response *map,
                                   const struct limine_hhdm_response *hhdm);
bool htmlk_m4_iso_accept_fault(unsigned vector, uint64_t rip, uint64_t cs,
                              uint64_t rsp, uint64_t ss, uint64_t error,
                              uint64_t cr2);
extern const unsigned char htmlk_m4_iso_bad_begin[];
extern const unsigned char htmlk_m4_iso_bad_end[];
extern const unsigned char htmlk_m4_iso_good_begin[];
extern const unsigned char htmlk_m4_iso_good_end[];
#endif
