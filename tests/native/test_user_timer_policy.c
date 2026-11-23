#include "user_timer_policy.h"
#include "user_pages.h"
#include "page_pool.h"
#include "isolation_policy.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static uint8_t kernel_stack[16384] __attribute__((aligned(16)));
int main(void) {
    const uintptr_t base = (uintptr_t)kernel_stack;
    struct htmlk_m4_irq_frame *f =
        (void *)(base + sizeof(kernel_stack) - sizeof(*f));
    memset(f, 0, sizeof(*f));
    f->rip = HTMLK_M4_USER_BASE;
    f->rsp = HTMLK_M4_USER_STACK - 16U;
    f->cs = HTMLK_M4_ISO_USER_CS;
    f->ss = HTMLK_M4_ISO_USER_SS;
    f->rflags = 0x202U;
    assert(htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    assert(!htmlk_m4_d_frame_valid(NULL, base, sizeof(kernel_stack), 36U));
    assert(!htmlk_m4_d_frame_valid(f, base, 64U, 36U));
    assert(!htmlk_m4_d_frame_valid(f, base, 16385U, 36U));
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 0));
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 4097U));
    assert(!htmlk_m4_d_frame_valid(f, UINTPTR_MAX - 7U, 8192U, 36U));
    assert(!htmlk_m4_d_frame_valid(f, base + 4096U, 256U, 36U));
    f->cs = 0x08U;
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->cs = HTMLK_M4_ISO_USER_CS;
    f->ss = 0x10U;
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->ss = HTMLK_M4_ISO_USER_SS;
    f->rip = HTMLK_M4_USER_BASE + 36U;
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->rip = HTMLK_M4_USER_BASE;
    f->rsp = HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE;
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->rsp = HTMLK_M4_USER_STACK - 16U;
    f->rflags = 0x2U; /* IF cleared, cannot be x2APIC time-sliced */
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->rflags = 0x3202U; /* User IOPL would break privileged I/O policy */
    assert(!htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    f->rflags = 0x202U;
    assert(htmlk_m4_d_frame_valid(f, base, sizeof(kernel_stack), 36U));
    puts("M4-D USER IRQ FRAME ABI NEGATIVE POLICY PASS");
    return 0;
}
