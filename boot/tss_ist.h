/* Opt-in M3 64-bit TSS and separate IST stacks for exception delivery.
 * Ring-0 only, no hardware IRQ enable, no SMP or user-space privilege transitions.
 */
#ifndef HTMLK_TSS_IST_H
#define HTMLK_TSS_IST_H

#include <stdbool.h>
#include <stdint.h>

struct __attribute__((packed)) htmlk_tss64 {
    uint32_t reserved0;
    uint64_t rsp[3];
    uint64_t reserved1;
    uint64_t ist[7];
    uint64_t reserved2;
    uint16_t reserved3;
    uint16_t io_bitmap_base;
};
_Static_assert(sizeof(struct htmlk_tss64) == 104, "AMD64 TSS must be 104 bytes");

struct __attribute__((packed)) htmlk_tss_descriptor {
    uint16_t limit_low;
    uint16_t base_low;
    uint8_t base_middle;
    uint8_t access;
    uint8_t limit_high_flags;
    uint8_t base_high;
    uint32_t base_upper;
    uint32_t reserved;
};
_Static_assert(sizeof(struct htmlk_tss_descriptor) == 16,
               "64-bit TSS GDT descriptor must be 16 bytes");

/* Pure descriptor builder for independent GCC UBSan host tests. */
bool htmlk_tss_descriptor_make(struct htmlk_tss_descriptor *out,
                               uint64_t tss_base, uint32_t limit);

/* Privileged real CPU GDT/TSS setup, BEFORE IDT with IST gate flags. */
void htmlk_tss_ist_install(void);
bool htmlk_tss_on_double_fault_stack(uint64_t current_rsp);
bool htmlk_tss_on_page_fault_stack(uint64_t current_rsp);

/* Only for a specially built QEMU negative-control image. */
#ifdef HTMLK_M3_DOUBLE_FAULT_TEST
__attribute__((noreturn)) void htmlk_tss_inject_double_fault(void);
#endif

#endif
