#include "preempt_x2apic.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Explicitly opt-in, test-only x2APIC MSR timer, single vCPU QEMU x86-64.
 * Other CPU state, isolated addresses, preemptive user mode NOT supported. */
#define M4_STACK_WORDS 2048U
#define M4_MAX_INTERRUPTS 256U
#define MSR_APIC_BASE 0x1bU
#define MSR_X2APIC_TPR 0x808U
#define MSR_X2APIC_EOI 0x80bU
#define MSR_X2APIC_SVR 0x80fU
#define MSR_X2APIC_LVT_TIMER 0x832U
#define MSR_X2APIC_INIT_COUNT 0x838U
#define MSR_X2APIC_DIVIDE 0x83eU

static uint64_t task_stack[HTMLK_M4_TASK_COUNT][M4_STACK_WORDS]
    __attribute__((aligned(16)));
static uint64_t *task_saved[HTMLK_M4_TASK_COUNT];
uint64_t *htmlk_m4_main_stack;
static volatile uint64_t progress[HTMLK_M4_TASK_COUNT];
static volatile uint64_t grants[HTMLK_M4_TASK_COUNT];
static volatile uint64_t done[HTMLK_M4_TASK_COUNT];
static unsigned current_id;
static uint64_t irq_count, switch_count;
#define M4_STACK_CANARY 0xB16B00B5FA1C0A11ULL

static void port_out(uint16_t port, uint8_t byte) {
    __asm__ volatile ("outb %0, %1" : : "a"(byte), "Nd"(port) : "memory");
}
static void print(const char *s) {
    while (*s) port_out(0xe9U, (uint8_t)*s++);
}
__attribute__((noreturn))
static void fail(const char *s) {
    __asm__ volatile ("cli" ::: "memory");
    print(s);
#ifdef HTMLK_QEMU_TEST_EXIT
    port_out(0xf4U, 0x19U); /* 51 = (0x19 << 1) | 1, failure. */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static uint64_t rdmsr(uint32_t msr) {
    uint32_t lo, hi;
    __asm__ volatile ("rdmsr" : "=a"(lo), "=d"(hi) : "c"(msr));
    return ((uint64_t)hi << 32) | lo;
}
static void wrmsr(uint32_t msr, uint64_t v) {
    __asm__ volatile ("wrmsr" : : "c"(msr),
                      "a"((uint32_t)v), "d"((uint32_t)(v >> 32)) : "memory");
}
static bool cpu_supports_x2apic(void) {
    uint32_t eax, ebx, ecx, edx;
    __asm__ volatile ("cpuid" : "=a"(eax), "=b"(ebx),
                      "=c"(ecx), "=d"(edx) : "a"(1U), "c"(0U));
    (void)eax; (void)ebx;
    return (edx & (1U << 9)) != 0 && (ecx & (1U << 21)) != 0;
}
static void apic_init(void) {
    __asm__ volatile ("cli" ::: "memory");
    if (!cpu_supports_x2apic()) fail("M4_X2APIC_UNSUPPORTED\n");
    const uint64_t base = rdmsr(MSR_APIC_BASE);
    if ((base & (1ULL << 11)) == 0) fail("M4_X2APIC_DISABLED\n");
    wrmsr(MSR_APIC_BASE, base | (1ULL << 10)); /* enable x2APIC MSRs */
    if ((rdmsr(MSR_APIC_BASE) & (3ULL << 10)) != (3ULL << 10))
        fail("M4_X2APIC_NOT_ACTIVE\n");
    /* Mask both legacy PICs. No IOAPIC or other external IRQ driver. */
    port_out(0x21U, 0xffU);
    port_out(0xa1U, 0xffU);
    wrmsr(MSR_X2APIC_TPR, 0);
    wrmsr(MSR_X2APIC_SVR, 0x1ffU); /* software enable, spurious vector FF */
    wrmsr(MSR_X2APIC_DIVIDE, 3U);  /* divide by 16 */
#ifdef HTMLK_M4_PREEMPT_TIMER_MASK_TEST
    wrmsr(MSR_X2APIC_LVT_TIMER, 0x30040U); /* masked periodic vector 0x40 */
#else
    wrmsr(MSR_X2APIC_LVT_TIMER, 0x20040U); /* periodic vector 0x40 */
#endif
    wrmsr(MSR_X2APIC_INIT_COUNT, 1000000U);
    print("M4_X2APIC_TIMER_READY\n");
}
static void apic_stop(void) {
    wrmsr(MSR_X2APIC_LVT_TIMER, 0x30040U);
    wrmsr(MSR_X2APIC_INIT_COUNT, 0);
}
static void task_body(unsigned id) {
    unsigned n = 0;
    /* No yield, hlt, blocking I/O or syscall. IRQ must preempt this busy loop. */
    for (;;) {
        if (n < HTMLK_M4_STEPS && grants[id] > n) {
            print(id == 0 ? "M4_PREEMPT_A_" : "M4_PREEMPT_B_");
            port_out(0xe9U, (uint8_t)('0' + n));
            port_out(0xe9U, (uint8_t)'\n');
            progress[id] = ++n;
            if (n == HTMLK_M4_STEPS) done[id] = 1;
        }
        __asm__ volatile ("pause" ::: "memory");
    }
}
__attribute__((noreturn))
static void task_a(void) {
    task_body(0U);
    __builtin_unreachable();
}
__attribute__((noreturn))
static void task_b(void) {
    task_body(1U);
    __builtin_unreachable();
}
__attribute__((noreturn))
static void unexpected_return(void) {
    fail("M4_TASK_RETURNED\n");
}
static uint64_t read_selector(bool code) {
    uint16_t value;
    if (code) __asm__ volatile ("mov %%cs, %0" : "=r"(value));
    else __asm__ volatile ("mov %%ss, %0" : "=r"(value));
    return value;
}
static void initialize_task(unsigned id, void (*entry)(void)) {
    uint64_t *top = &task_stack[id][M4_STACK_WORDS - 1U];
    *top = (uint64_t)(uintptr_t)&unexpected_return;
    struct htmlk_m4_irq_frame *f =
        (struct htmlk_m4_irq_frame *)((uint8_t *)top - sizeof(*f));
    uint64_t *words = (uint64_t *)f;
    for (unsigned i = 0; i < sizeof(*f) / sizeof(uint64_t); ++i)
        words[i] = 0;
    f->rip = (uint64_t)(uintptr_t)entry;
    f->cs = read_selector(true);
    f->ss = read_selector(false);
    f->rsp = (uint64_t)(uintptr_t)top;
    f->rflags = 0x202U; /* ring0 + interrupts enabled, reserved bit set */
    task_stack[id][0] = M4_STACK_CANARY;
    task_saved[id] = (uint64_t *)f;
}
static bool valid_task_frame(unsigned id, const uint64_t *stack) {
    if (id >= HTMLK_M4_TASK_COUNT || stack == NULL) return false;
    const uintptr_t lo = (uintptr_t)&task_stack[id][64U];
    const uintptr_t hi = (uintptr_t)&task_stack[id][M4_STACK_WORDS];
    const uintptr_t ptr = (uintptr_t)stack;
    return ptr >= lo && ptr <= hi - sizeof(struct htmlk_m4_irq_frame) &&
           (ptr & (sizeof(uint64_t) - 1U)) == 0 &&
           task_stack[id][0] == M4_STACK_CANARY;
}
uint64_t *htmlk_m4_on_timer_irq(uint64_t *stack) {
    if (current_id >= HTMLK_M4_TASK_COUNT || stack == NULL)
        fail("M4_BAD_INTERRUPT_CONTEXT\n");
    if (!valid_task_frame(current_id, stack))
        fail("M4_CURRENT_CONTEXT_OUT_OF_RANGE\n");
    task_saved[current_id] = stack;
    ++irq_count;
    if (irq_count > M4_MAX_INTERRUPTS)
        fail("M4_PREEMPT_TIMEOUT\n");
    const unsigned previous = current_id;
    /* Never skip a task's granted progress update before switching. */
    if (progress[previous] < grants[previous]) {
        wrmsr(MSR_X2APIC_EOI, 0);
        return stack;
    }
    if (done[0] != 0 && done[1] != 0) {
        if (progress[0] != HTMLK_M4_STEPS ||
            progress[1] != HTMLK_M4_STEPS || switch_count < 5U)
            fail("M4_PREEMPT_BAD_COMPLETION\n");
        apic_stop();
        wrmsr(MSR_X2APIC_EOI, 0);
        print("M4_X2APIC_PREEMPT_PASS\n");
        return NULL; /* special assembly exit back to saved main stack */
    }
    unsigned next = previous ^ 1U;
    if (done[next]) next = previous;
    if (done[previous] && next == previous)
        fail("M4_BOTH_TASKS_NOT_RUNNABLE\n");
    if (progress[next] >= grants[next] && grants[next] < HTMLK_M4_STEPS)
        ++grants[next];
    if (next != previous) ++switch_count;
    if (!valid_task_frame(next, task_saved[next]))
        fail("M4_NEXT_CONTEXT_OUT_OF_RANGE\n");
    current_id = next;
    wrmsr(MSR_X2APIC_EOI, 0);
    return task_saved[next];
}
void htmlk_m4_preempt_probe(void) {
    __asm__ volatile ("cli" ::: "memory");
    progress[0] = progress[1] = 0;
    grants[0] = 1;
    grants[1] = 0;
    done[0] = done[1] = 0;
    current_id = 0;
    irq_count = switch_count = 0;
    initialize_task(0, &task_a);
    initialize_task(1, &task_b);
    if (task_saved[0] == task_saved[1] ||
        !valid_task_frame(0, task_saved[0]) ||
        !valid_task_frame(1, task_saved[1]))
        fail("M4_INVALID_INITIAL_CONTEXT\n");
#ifdef HTMLK_M4_PREEMPT_BAD_FRAME_TEST
    /* Test only: inject invalid pointer, verify rejection before any CPU jump. */
    if (!valid_task_frame(1, (uint64_t *)((uintptr_t)task_saved[1] + 1U)))
        fail("M4_PREEMPT_BAD_FRAME_REJECTED\n");
    fail("M4_PREEMPT_BAD_FRAME_ACCEPTED\n");
#endif
    apic_init();
    htmlk_m4_enter_first(task_saved[0]);
    __asm__ volatile ("cli" ::: "memory");
    if (!done[0] || !done[1] || switch_count < 5U)
        fail("M4_PREEMPT_MAIN_RETURN_INVALID\n");
    print("M4_PREEMPT_MAIN_RESTORED\n");
}
