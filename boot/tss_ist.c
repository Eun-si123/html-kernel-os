/* M3 x86-64 TSS, GDT, IST1 (#DF) and IST2 (#PF) demonstration.
 * The active GDT is replaced only when explicitly requested by the build.
 * No external IRQ is enabled or serviced, no user/ring3 transitions.
 */
#include "tss_ist.h"
#include <stddef.h>
#include <stdint.h>

_Static_assert(offsetof(struct htmlk_tss64, ist) == 36,
               "hardware IST1 offset must be 36");
_Static_assert(offsetof(struct htmlk_tss64, io_bitmap_base) == 102,
               "hardware IOPB offset must be 102");

enum { IST_STACK_BYTES = 16384 };
static uint8_t df_stack[IST_STACK_BYTES] __attribute__((aligned(16)));
static uint8_t pf_stack[IST_STACK_BYTES] __attribute__((aligned(16)));
#if defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION)
static uint8_t user_kernel_stack[IST_STACK_BYTES] __attribute__((aligned(16)));
#endif
static struct htmlk_tss64 tss __attribute__((aligned(16)));

/* 64-bit code selector 0x08; data selector 0x10; TSS selector 0x18. */
static uint64_t gdt[7] __attribute__((aligned(16))) = {
    0,
    UINT64_C(0x00af9a000000ffff),
    UINT64_C(0x00cf92000000ffff),
    0, 0,
#if defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION) || \
    defined(HTMLK_M4_USER_PREEMPT)
    UINT64_C(0x00affa000000ffff), /* selector 0x2b: ring 3 CS */
    UINT64_C(0x00cff2000000ffff)  /* selector 0x33: ring 3 SS */
#else
    0, 0
#endif
};

struct __attribute__((packed)) gdtr {
    uint16_t limit;
    uint64_t base;
};
_Static_assert(sizeof(struct gdtr) == 10, "x86-64 LGDT pointer is 10 bytes");

static void report(const char *msg) {
    while (*msg != 0) {
        const uint8_t ch = (uint8_t)*msg++;
        __asm__ volatile ("outb %0, %1" : :
                          "a"(ch), "Nd"((unsigned short)0xe9));
    }
}

bool htmlk_tss_descriptor_make(struct htmlk_tss_descriptor *out,
                               uint64_t tss_base, uint32_t limit) {
    if (out == 0 || tss_base == 0 || limit < 103 || limit > 0xfffff) {
        return false;
    }
    const uint64_t high = tss_base >> 48;
    const bool negative = (tss_base & (UINT64_C(1) << 47)) != 0;
    if (high != (negative ? 0xffffU : 0U)) return false;
    out->limit_low = (uint16_t)limit;
    out->base_low = (uint16_t)tss_base;
    out->base_middle = (uint8_t)(tss_base >> 16);
    out->access = 0x89; /* present, ring0, available 64-bit TSS */
    out->limit_high_flags = (uint8_t)((limit >> 16) & 15U);
    out->base_high = (uint8_t)(tss_base >> 24);
    out->base_upper = (uint32_t)(tss_base >> 32);
    out->reserved = 0;
    return true;
}

bool htmlk_tss_on_double_fault_stack(uint64_t rsp) {
    const uint64_t first = (uint64_t)(uintptr_t)&df_stack[0];
    return rsp >= first && rsp < first + IST_STACK_BYTES;
}

bool htmlk_tss_on_page_fault_stack(uint64_t rsp) {
    const uint64_t first = (uint64_t)(uintptr_t)&pf_stack[0];
    return rsp >= first && rsp < first + IST_STACK_BYTES;
}

__attribute__((noinline))
void htmlk_tss_ist_install(void) {
    __asm__ volatile ("cli" ::: "memory");
#if defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION)
    tss.rsp[0] = (uint64_t)(uintptr_t)&user_kernel_stack[IST_STACK_BYTES];
#else
    tss.rsp[0] = (uint64_t)(uintptr_t)&pf_stack[IST_STACK_BYTES];
#endif
    tss.ist[0] = (uint64_t)(uintptr_t)&df_stack[IST_STACK_BYTES];
    tss.ist[1] = (uint64_t)(uintptr_t)&pf_stack[IST_STACK_BYTES];
    tss.io_bitmap_base = (uint16_t)sizeof(tss);

    struct htmlk_tss_descriptor descriptor;
    if (!htmlk_tss_descriptor_make(&descriptor,
                                  (uint64_t)(uintptr_t)&tss,
                                  (uint32_t)(sizeof(tss) - 1U))) {
        report("M3_TSS_DESCRIPTOR_INVALID\n");
        __asm__ volatile ("cli");
        for (;;) __asm__ volatile ("hlt");
    }
    const uint8_t *source = (const uint8_t *)(const void *)&descriptor;
    uint8_t *destination = (uint8_t *)(void *)&gdt[3];
    for (unsigned i = 0; i < 16; ++i) destination[i] = source[i];
    const struct gdtr pointer = {
        .limit = (uint16_t)(sizeof(gdt) - 1),
        .base = (uint64_t)(uintptr_t)&gdt[0]
    };
    __asm__ volatile ("lgdt %0" : : "m"(pointer) : "memory");

    /* Limine may use a different CS selector. Far return reloads CS=0x08
     * under our new GDT before any exception gate is installed.
     * The currently valid Limine page table and stack are preserved.
     */
    __asm__ volatile (
        "pushq $0x08\n\t"
        "leaq 1f(%%rip), %%rax\n\t"
        "pushq %%rax\n\t"
        "lretq\n\t"
        "1:\n\t"
        "movw $0x10, %%ax\n\t"
        "movw %%ax, %%ds\n\t"
        "movw %%ax, %%es\n\t"
        "movw %%ax, %%ss\n\t"
        : : : "rax", "memory"
    );
    const uint16_t tss_selector = 0x18;
    __asm__ volatile ("ltr %w0" : : "r"(tss_selector) : "memory");
    report("M3_TSS_IST_READY\n");
}

#ifdef HTMLK_M4_USER_PREEMPT
bool htmlk_tss_set_rsp0(uint64_t top) {
    if (!top || (top & 15U) != 0 ||
        (top >> 48) != ((top & (UINT64_C(1) << 47)) ? 0xffffU : 0U))
        return false;
    tss.rsp[0] = top;
    return tss.rsp[0] == top;
}
#endif

#ifdef HTMLK_M3_DOUBLE_FAULT_TEST
__attribute__((noreturn, noinline))
void htmlk_tss_inject_double_fault(void) {
    /* Deliberately corrupt *only* test image's IST2 pointer, not the
     * current stack. A genuine unmapped read raises #PF; delivery cannot
     * push its frame on IST2, so the CPU must enter #DF on intact IST1.
     * This tests faults *during exception delivery*, not recursive faults
     * while a handler is already running.
     */
    tss.ist[1] = UINT64_C(0x0000000040000000);
    __asm__ volatile ("" : : : "memory");
    __asm__ volatile (
        "movabs $0x0000000050000000, %%rax\n\t"
        "mov (%%rax), %%rax\n\t"
        : : : "rax", "memory"
    );
    report("M3_DOUBLE_FAULT_NOT_TRIGGERED\n");
    __asm__ volatile ("outb %0, %1" : :
                      "a"((uint8_t)0x17), "Nd"((unsigned short)0xf4));
    for (;;) __asm__ volatile ("cli; hlt");
}
#endif
