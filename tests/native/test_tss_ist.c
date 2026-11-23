#include "tss_ist.h"
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CHECK(x) do { \
    if (!(x)) { \
        (void)fprintf(stderr, "M3 TSS descriptor line %d failed: %s\n", __LINE__, #x); \
        return 1; \
    } \
} while (0)

int main(void) {
    CHECK(sizeof(struct htmlk_tss64) == 104);
    CHECK(offsetof(struct htmlk_tss64, ist) == 36);
    CHECK(offsetof(struct htmlk_tss64, io_bitmap_base) == 102);
    struct htmlk_tss_descriptor actual = {0};
    CHECK(htmlk_tss_descriptor_make(
        &actual, UINT64_C(0xffffffff80008000), 103));
    CHECK(actual.limit_low == 103);
    CHECK(actual.base_low == 0x8000);
    CHECK(actual.base_middle == 0);
    CHECK(actual.base_high == 0x80);
    CHECK(actual.base_upper == UINT32_C(0xffffffff));
    CHECK(actual.access == 0x89);
    CHECK(actual.limit_high_flags == 0);
    CHECK(actual.reserved == 0);
    struct htmlk_tss_descriptor old = actual;
    CHECK(!htmlk_tss_descriptor_make(0, 0x1234, 103));
    CHECK(!htmlk_tss_descriptor_make(&actual, 0, 103));
    CHECK(!htmlk_tss_descriptor_make(&actual, 0x1234, 102));
    CHECK(!htmlk_tss_descriptor_make(&actual, 0x1234, 0x100000));
    CHECK(!htmlk_tss_descriptor_make(&actual, UINT64_C(0x0000800000000000), 103));
    CHECK(!htmlk_tss_descriptor_make(&actual, UINT64_C(0xffff000000000000), 103));
    CHECK(memcmp(&actual, &old, sizeof(actual)) == 0);
    CHECK(htmlk_tss_descriptor_make(&actual, 0x00007fffffffffffULL, 103));
    CHECK(actual.base_upper == 0x00007fff);
    CHECK(!htmlk_tss_on_double_fault_stack(0));
    CHECK(!htmlk_tss_on_page_fault_stack(0));
    (void)puts("M3 TSS/IST DESCRIPTOR HOST CONTRACT PASS");
    return 0;
}
