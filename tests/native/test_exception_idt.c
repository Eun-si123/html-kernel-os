/* Pure gate-construction tests; never uses privileged lidt on the host. */
#include "exception_idt.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CHECK(condition) do { \
    if (!(condition)) { \
        (void)fprintf(stderr, "IDT gate contract failure line %d: %s\n", \
                      __LINE__, #condition); \
        return 1; \
    } \
} while (0)

int main(void) {
    struct htmlk_idt_gate gate;
    CHECK(htmlk_idt_gate_make(
        &gate, UINT64_C(0xffffffff80001234), (uint16_t)0x28));
    CHECK(gate.offset_low == 0x1234);
    CHECK(gate.offset_mid == 0x8000);
    CHECK(gate.offset_high == UINT32_C(0xffffffff));
    CHECK(gate.selector == 0x28);
    CHECK(gate.type_attributes == 0x8e);
    CHECK(gate.ist == 0);
    CHECK(gate.reserved == 0);
    CHECK(((uint64_t)gate.offset_high << 32 |
           (uint64_t)gate.offset_mid << 16 | gate.offset_low) ==
          UINT64_C(0xffffffff80001234));

    struct htmlk_idt_gate old = gate;
    CHECK(!htmlk_idt_gate_make(0, UINT64_C(0xffffffff80001234), 0x28));
    CHECK(!htmlk_idt_gate_make(&gate, 0, 0x28));
    CHECK(!htmlk_idt_gate_make(&gate, 0x1234, 0));
    CHECK(!htmlk_idt_gate_make(&gate, UINT64_C(0x0000800000000000), 0x28));
    CHECK(!htmlk_idt_gate_make(&gate, UINT64_C(0xffff000000000000), 0x28));
    CHECK(memcmp(&old, &gate, sizeof(gate)) == 0);
    CHECK(htmlk_idt_gate_make(
        &gate, UINT64_C(0x00007fffffffffff), 0x08));
    CHECK(gate.offset_low == 0xffff);
    CHECK(gate.offset_mid == 0xffff);
    CHECK(gate.offset_high == 0x00007fff);
    CHECK(gate.type_attributes == 0x8e);
    (void)puts("M3 IDT DESCRIPTOR NATIVE CONTRACT PASS");
    return 0;
}
