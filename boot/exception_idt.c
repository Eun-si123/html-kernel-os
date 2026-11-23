/* Opt-in x86-64 exception capture. Uses GCC interrupt ABI and the x86-64
 * baseline ISA (-mgeneral-regs-only, -mno-red-zone in the boot build).
 * Does not support recovery, interrupts, SMP, TSS, IST or user mode.
 */
#include "exception_idt.h"
#if defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION)
#include "user_probe.h"
#endif
#ifdef HTMLK_M4_USER_ISOLATION
#include "user_isolation.h"
#endif
#ifdef HTMLK_M4_USER_PREEMPT
#include "user_preempt.h"
#endif
#ifdef HTMLK_M4_X2APIC_PREEMPT
#include "preempt_x2apic.h"
#endif
#ifdef HTMLK_M4_TIMER_PROBE
#include "timer_irq.h"
#endif
#ifdef HTMLK_M3_IST_STACK
#include "tss_ist.h"
#endif
#ifdef HTMLK_M3_PAGING_RECOVER_TEST
#include "paging_probe.h"
#endif
#include <stdint.h>

struct __attribute__((packed)) idtr {
    uint16_t limit;
    uint64_t base;
};
_Static_assert(sizeof(struct idtr) == 10, "x86-64 lidt pointer must be 10 bytes");

struct interrupt_frame {
    uint64_t rip;
    uint64_t cs;
    uint64_t rflags;
    uint64_t rsp;
    uint64_t ss;
};

static struct htmlk_idt_gate idt[256];

bool htmlk_idt_gate_make(struct htmlk_idt_gate *gate,
                         uint64_t handler_address, uint16_t cs_selector) {
    if (gate == 0 || handler_address == 0 || (cs_selector & 0xfffcU) == 0) {
        return false;
    }
    /* Long mode's 48-bit canonical-address rule for this 4-level build. */
    const uint64_t sign = (handler_address >> 47) & 1U;
    if ((handler_address >> 48) != (sign ? 0xffffU : 0U)) {
        return false;
    }
    gate->offset_low = (uint16_t)handler_address;
    gate->selector = cs_selector;
    gate->ist = 0;
    gate->type_attributes = 0x8e; /* present, DPL0, 64-bit interrupt gate */
    gate->offset_mid = (uint16_t)(handler_address >> 16);
    gate->offset_high = (uint32_t)(handler_address >> 32);
    gate->reserved = 0;
    return true;
}

static void io_char(uint8_t byte) {
    __asm__ volatile ("outb %0, %1" : :
                      "a"(byte), "Nd"((unsigned short)0xe9));
    __asm__ volatile ("outb %0, %1" : :
                      "a"(byte), "Nd"((unsigned short)0x3f8));
}

static void io_string(const char *message) {
    while (*message) io_char((uint8_t)*message++);
}

static void io_hex(uint64_t value, unsigned digits) {
    const char hex[] = "0123456789ABCDEF";
    while (digits > 0) {
        --digits;
        io_char((uint8_t)hex[(value >> (digits * 4U)) & 15U]);
    }
}

__attribute__((noreturn, noinline))
static void panic(unsigned vector, uint64_t rip, uint64_t error_code) {
    __asm__ volatile ("cli" ::: "memory");
    io_string("M3_EXCEPTION V=");
    io_hex(vector, 2);
    io_string("\nM3_RIP=0x");
    io_hex(rip, 16);
    io_string("\nM3_ERROR=0x");
    io_hex(error_code, 16);
    io_char('\n');
    if (vector == 14U) {
        uint64_t cr2;
        __asm__ volatile ("mov %%cr2, %0" : "=r"(cr2));
        io_string("M3_CR2=0x");
        io_hex(cr2, 16);
        io_char('\n');
    }
#ifdef HTMLK_QEMU_TEST_EXIT
    /* Non-success QEMU isa-debug-exit status: (0x16 << 1) | 1 = 45. */
    __asm__ volatile ("outb %0, %1" : :
                      "a"((uint8_t)0x16), "Nd"((unsigned short)0xf4));
#endif
    for (;;) {
        __asm__ volatile ("hlt" ::: "memory");
    }
}

/* CPU error-code vectors: 8, 10-14, 17, 21, 29, 30. All others
 * use the GCC no-error-code interrupt signature. These handlers are
 * intentionally fail-stop and never attempt iretq/recovery.
 */
__attribute__((interrupt)) static void vector_0(struct interrupt_frame *f) {
    panic(0, f->rip, 0);
}

__attribute__((interrupt)) static void vector_1(struct interrupt_frame *f) {
    panic(1, f->rip, 0);
}

__attribute__((interrupt)) static void vector_2(struct interrupt_frame *f) {
    panic(2, f->rip, 0);
}

__attribute__((interrupt)) static void vector_3(struct interrupt_frame *f) {
    panic(3, f->rip, 0);
}

__attribute__((interrupt)) static void vector_4(struct interrupt_frame *f) {
    panic(4, f->rip, 0);
}

__attribute__((interrupt)) static void vector_5(struct interrupt_frame *f) {
    panic(5, f->rip, 0);
}

__attribute__((interrupt)) static void vector_6(struct interrupt_frame *f) {
    panic(6, f->rip, 0);
}

__attribute__((interrupt)) static void vector_7(struct interrupt_frame *f) {
    panic(7, f->rip, 0);
}

__attribute__((interrupt)) static void vector_8(struct interrupt_frame *f, unsigned long code) {
#ifdef HTMLK_M3_IST_STACK
    uint64_t current_rsp;
    __asm__ volatile ("mov %%rsp, %0" : "=r"(current_rsp));
    io_string(htmlk_tss_on_double_fault_stack(current_rsp)
              ? "M3_IST_DF_STACK_OK\n" : "M3_IST_DF_STACK_BAD\n");
#endif
    panic(8, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_9(struct interrupt_frame *f) {
    panic(9, f->rip, 0);
}

__attribute__((interrupt)) static void vector_10(struct interrupt_frame *f, unsigned long code) {
    panic(10, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_11(struct interrupt_frame *f, unsigned long code) {
    panic(11, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_12(struct interrupt_frame *f, unsigned long code) {
    panic(12, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_13(struct interrupt_frame *f, unsigned long code) {
#ifdef HTMLK_M4_USER_ISOLATION
    if (htmlk_m4_iso_accept_fault(13U, f->rip, f->cs, f->rsp, f->ss,
                                  (uint64_t)code, 0U))
        htmlk_m4_user_return(); /* abandon faulted user, trusted main stack */
#endif
    panic(13, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_14(struct interrupt_frame *f, unsigned long code) {
#ifdef HTMLK_M3_IST_STACK
    uint64_t current_rsp;
    __asm__ volatile ("mov %%rsp, %0" : "=r"(current_rsp));
    io_string(htmlk_tss_on_page_fault_stack(current_rsp)
              ? "M3_IST_PF_STACK_OK\n" : "M3_IST_PF_STACK_BAD\n");
#endif
#ifdef HTMLK_M3_PAGING_RECOVER_TEST
    uint64_t fault_address;
    __asm__ volatile ("mov %%cr2, %0" : "=r"(fault_address));
    if (htmlk_paging_recover_page_fault(fault_address, (uint64_t)code)) {
        return; /* architectural iretq retries the original CPU load */
    }
#endif
#ifdef HTMLK_M4_USER_ISOLATION
    uint64_t fault_cr2;
    __asm__ volatile ("mov %%cr2,%0" : "=r"(fault_cr2));
    if (htmlk_m4_iso_accept_fault(14U, f->rip, f->cs, f->rsp, f->ss,
                                  (uint64_t)code, fault_cr2))
        htmlk_m4_user_return(); /* abandon IST frame and private CR3 */
#endif
#ifdef HTMLK_M4_USER_PREEMPT
    uint64_t user_preempt_cr2;
    __asm__ volatile ("mov %%cr2,%0" : "=r"(user_preempt_cr2));
    if (htmlk_m4_d_accept_fault(14U, f->rip, f->cs, f->rflags,
                                f->rsp, f->ss, (uint64_t)code,
                                user_preempt_cr2))
        htmlk_m4_d_retire_fault(); /* exits IST2 onto trusted main stack */
#endif
    panic(14, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_15(struct interrupt_frame *f) {
    panic(15, f->rip, 0);
}

__attribute__((interrupt)) static void vector_16(struct interrupt_frame *f) {
    panic(16, f->rip, 0);
}

__attribute__((interrupt)) static void vector_17(struct interrupt_frame *f, unsigned long code) {
    panic(17, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_18(struct interrupt_frame *f) {
    panic(18, f->rip, 0);
}

__attribute__((interrupt)) static void vector_19(struct interrupt_frame *f) {
    panic(19, f->rip, 0);
}

__attribute__((interrupt)) static void vector_20(struct interrupt_frame *f) {
    panic(20, f->rip, 0);
}

__attribute__((interrupt)) static void vector_21(struct interrupt_frame *f, unsigned long code) {
    panic(21, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_22(struct interrupt_frame *f) {
    panic(22, f->rip, 0);
}

__attribute__((interrupt)) static void vector_23(struct interrupt_frame *f) {
    panic(23, f->rip, 0);
}

__attribute__((interrupt)) static void vector_24(struct interrupt_frame *f) {
    panic(24, f->rip, 0);
}

__attribute__((interrupt)) static void vector_25(struct interrupt_frame *f) {
    panic(25, f->rip, 0);
}

__attribute__((interrupt)) static void vector_26(struct interrupt_frame *f) {
    panic(26, f->rip, 0);
}

__attribute__((interrupt)) static void vector_27(struct interrupt_frame *f) {
    panic(27, f->rip, 0);
}

__attribute__((interrupt)) static void vector_28(struct interrupt_frame *f) {
    panic(28, f->rip, 0);
}

__attribute__((interrupt)) static void vector_29(struct interrupt_frame *f, unsigned long code) {
    panic(29, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_30(struct interrupt_frame *f, unsigned long code) {
    panic(30, f->rip, (uint64_t)code);
}

__attribute__((interrupt)) static void vector_31(struct interrupt_frame *f) {
    panic(31, f->rip, 0);
}

void htmlk_idt_install(void) {
    uint16_t cs;
    __asm__ volatile ("cli; mov %%cs, %0" : "=r"(cs) : : "memory");
    static const uint64_t handlers[32] = {
        (uint64_t)(uintptr_t)&vector_0,
        (uint64_t)(uintptr_t)&vector_1,
        (uint64_t)(uintptr_t)&vector_2,
        (uint64_t)(uintptr_t)&vector_3,
        (uint64_t)(uintptr_t)&vector_4,
        (uint64_t)(uintptr_t)&vector_5,
        (uint64_t)(uintptr_t)&vector_6,
        (uint64_t)(uintptr_t)&vector_7,
        (uint64_t)(uintptr_t)&vector_8,
        (uint64_t)(uintptr_t)&vector_9,
        (uint64_t)(uintptr_t)&vector_10,
        (uint64_t)(uintptr_t)&vector_11,
        (uint64_t)(uintptr_t)&vector_12,
        (uint64_t)(uintptr_t)&vector_13,
        (uint64_t)(uintptr_t)&vector_14,
        (uint64_t)(uintptr_t)&vector_15,
        (uint64_t)(uintptr_t)&vector_16,
        (uint64_t)(uintptr_t)&vector_17,
        (uint64_t)(uintptr_t)&vector_18,
        (uint64_t)(uintptr_t)&vector_19,
        (uint64_t)(uintptr_t)&vector_20,
        (uint64_t)(uintptr_t)&vector_21,
        (uint64_t)(uintptr_t)&vector_22,
        (uint64_t)(uintptr_t)&vector_23,
        (uint64_t)(uintptr_t)&vector_24,
        (uint64_t)(uintptr_t)&vector_25,
        (uint64_t)(uintptr_t)&vector_26,
        (uint64_t)(uintptr_t)&vector_27,
        (uint64_t)(uintptr_t)&vector_28,
        (uint64_t)(uintptr_t)&vector_29,
        (uint64_t)(uintptr_t)&vector_30,
        (uint64_t)(uintptr_t)&vector_31,
    };
    for (unsigned i = 0; i < 32; ++i) {
        if (!htmlk_idt_gate_make(&idt[i], handlers[i], cs)) {
            panic(13, 0, 0); /* impossible on a valid Limine long-mode handoff */
        }
    }
#ifdef HTMLK_M3_IST_STACK
    idt[8].ist = 1;  /* #DF uses its own dedicated stack even if RSP is broken */
    idt[14].ist = 2; /* #PF never shares the double-fault emergency stack */
#endif
#ifdef HTMLK_M4_TIMER_PROBE
    if (!htmlk_idt_gate_make(&idt[32],
            (uint64_t)(uintptr_t)&htmlk_m4_irq0_entry, cs)) {
        panic(13, 0, 0);
    }
#endif
#if defined(HTMLK_M4_X2APIC_PREEMPT) || defined(HTMLK_M4_USER_PREEMPT)
    if (!htmlk_idt_gate_make(&idt[HTMLK_M4_PREEMPT_VECTOR],
            (uint64_t)(uintptr_t)&htmlk_m4_x2apic_irq_entry, cs) ||
        !htmlk_idt_gate_make(&idt[0xffU],
            (uint64_t)(uintptr_t)&htmlk_m4_x2apic_spurious_entry, cs)) {
        panic(13, 0, 0);
    }
#endif
#ifdef HTMLK_M4_USER_PREEMPT
    if (!htmlk_idt_gate_make(&idt[0x80U],
            (uint64_t)(uintptr_t)&htmlk_m4_d_syscall_entry, cs)) {
        panic(13, 0, 0);
    }
    idt[0x80U].type_attributes = 0xeeU; /* real DPL3: CPL3 INT 0x80 */
#elif defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION)
    if (!htmlk_idt_gate_make(&idt[0x80U],
            (uint64_t)(uintptr_t)&htmlk_m4_syscall_entry, cs)) {
        panic(13, 0, 0);
    }
    idt[0x80U].type_attributes = 0xeeU; /* DPL3 interrupt gate, CPL switch uses TSS.RSP0 */
#endif
    const struct idtr pointer = { (uint16_t)(sizeof(idt) - 1), (uint64_t)(uintptr_t)idt };
    __asm__ volatile ("lidt %0" : : "m"(pointer) : "memory");
    io_string("M3_IDT_READY\n");
}

/* Explicitly test the real CPU's exception-dispatch path, not a fake call
 * to panic. A fault never returns to kernel_main (source-generated HTML).
 */
#if defined(HTMLK_M3_FAULT_UD) || defined(HTMLK_M3_FAULT_PF) || \
    defined(HTMLK_M3_FAULT_DE) || defined(HTMLK_M3_FAULT_GP)
void htmlk_idt_inject_test_fault(void) {
#ifdef HTMLK_M3_FAULT_UD
    __asm__ volatile ("ud2" ::: "memory");
#elif defined(HTMLK_M3_FAULT_PF)
    __asm__ volatile ("movabs $0x40000000, %%rax; mov (%%rax), %%rax"
                      : : : "rax", "memory");
#elif defined(HTMLK_M3_FAULT_DE)
    __asm__ volatile ("mov $1, %%rax; xor %%rdx, %%rdx; xor %%rcx, %%rcx; div %%rcx"
                      : : : "rax", "rcx", "rdx", "memory");
#elif defined(HTMLK_M3_FAULT_GP)
    __asm__ volatile ("movabs $0x0000800000000000, %%rax; mov (%%rax), %%rax"
                      : : : "rax", "memory");
#endif
    /* Fault injection unexpectedly returned: it must not pass QEMU tests. */
    panic(0xff, 0, 0);
}
#endif
