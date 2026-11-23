/* M3 x86-64 exception IDT: opt-in, ring-0 only, no scheduler/IRQ support. */
#ifndef HTMLK_EXCEPTION_IDT_H
#define HTMLK_EXCEPTION_IDT_H

#include <stdbool.h>
#include <stdint.h>

/* AMD64 interrupt-gate layout: 16 bytes. */
struct __attribute__((packed)) htmlk_idt_gate {
    uint16_t offset_low;
    uint16_t selector;
    uint8_t ist;
    uint8_t type_attributes;
    uint16_t offset_mid;
    uint32_t offset_high;
    uint32_t reserved;
};
_Static_assert(sizeof(struct htmlk_idt_gate) == 16, "x86-64 IDT gate must be 16 bytes");

/* Pure, independently host-testable gate constructor. Never executes lidt. */
bool htmlk_idt_gate_make(struct htmlk_idt_gate *gate,
                         uint64_t handler_address, uint16_t cs_selector);

/* Install ring-0 trap handlers for architected exceptions 0..31.
 * This is fail-stop diagnostics, NOT recovery from CPU faults.
 * IRQs remain masked; no nested handlers, SMP, TSS/IST or page recovery. */
void htmlk_idt_install(void);

/* Test-only deterministic exception injection; no public HTML language API. */
#if defined(HTMLK_M3_FAULT_UD) || defined(HTMLK_M3_FAULT_PF) || \
    defined(HTMLK_M3_FAULT_DE) || defined(HTMLK_M3_FAULT_GP)
void htmlk_idt_inject_test_fault(void);
#endif

#endif
