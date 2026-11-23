#include "task_runtime.h"
#include "task_model.h"
#include <stdint.h>
/* Opt-in two independent ring-0 stacks. The C state model is host-testable. */
#define STACK_WORDS 1024U
#define MAX_DISPATCH 16U
static uint64_t stacks[HTMLK_M4_MAX_TASKS][STACK_WORDS]
    __attribute__((aligned(16)));
static uint64_t *saved_sp[HTMLK_M4_MAX_TASKS];
static uint64_t *scheduler_sp;
static struct htmlk_task_model tasks;
static unsigned running;
extern void htmlk_m4_context_switch(uint64_t **old_stack, uint64_t *new_stack);
static void log_char(uint8_t c) {
    __asm__ volatile ("outb %0, %1" : : "a"(c), "Nd"((unsigned short)0xe9));
}
static void log_text(const char *text) {
    while (*text != 0) log_char((uint8_t)*text++);
}
__attribute__((noreturn))
static void fail(const char *text) {
    log_text(text);
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0, %1" : :
                      "a"((uint8_t)0x17), "Nd"((unsigned short)0xf4));
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static void yield_to_scheduler(void) {
    if (!htmlk_task_yield_state(&tasks, running))
        fail("M4_INVALID_YIELD\n");
    htmlk_m4_context_switch(&saved_sp[running], scheduler_sp);
}
__attribute__((noreturn))
static void finish_task(void) {
    if (!htmlk_task_complete(&tasks, running))
        fail("M4_INVALID_EXIT\n");
    htmlk_m4_context_switch(&saved_sp[running], scheduler_sp);
    fail("M4_RESUMED_DEAD_TASK\n");
}
__attribute__((noreturn))
static void task_entry(void) {
    const unsigned id = running;
    /* Local values must remain correct across actual stack swaps. */
    volatile uint64_t token = id == 0U ? 0xA11CE5A11CE5ULL : 0xB00B5B00B5ULL;
    for (unsigned n = 0; n < 3; ++n) {
        if (running != id ||
            token != (id == 0U ? 0xA11CE5A11CE5ULL : 0xB00B5B00B5ULL))
            fail("M4_CONTEXT_CORRUPTED\n");
        log_text(id == 0U ? "M4_TASK_A_" : "M4_TASK_B_");
        log_char((uint8_t)('0' + n));
        log_char('\n');
        yield_to_scheduler();
    }
    finish_task();
}
__attribute__((noreturn))
static void task_return_trap(void) {
    fail("M4_TASK_RETURNED\n");
}
static void init_stack(unsigned id) {
    /* 16-byte aligned switch frame: six saved registers, then return IP.
     * Fake caller address yields ABI-correct %rsp=8 (mod 16) in task_entry. */
    uint64_t *sp = &stacks[id][STACK_WORDS];
    *--sp = (uint64_t)(uintptr_t)&task_return_trap;
    *--sp = (uint64_t)(uintptr_t)&task_entry;
    for (unsigned reg = 0; reg < 6; ++reg) *--sp = 0;
    saved_sp[id] = sp;
}
void htmlk_m4_task_probe(void) {
    __asm__ volatile ("cli" ::: "memory");
    htmlk_task_model_init(&tasks);
    if (!htmlk_task_create(&tasks, 0) || !htmlk_task_create(&tasks, 1))
        fail("M4_TASK_CREATE_FAILED\n");
#ifdef HTMLK_M4_TASK_NEGATIVE_TEST
    if (htmlk_task_create(&tasks, 0) ||
        htmlk_task_create(&tasks, HTMLK_M4_MAX_TASKS) ||
        htmlk_task_run(&tasks, HTMLK_M4_MAX_TASKS) ||
        htmlk_task_all_done(&tasks))
        fail("M4_TASK_NEGATIVE_ACCEPTED\n");
    log_text("M4_TASK_NEGATIVE_REJECTED\n");
#endif
    init_stack(0);
    init_stack(1);
    unsigned last = HTMLK_M4_MAX_TASKS - 1;
    for (unsigned count = 0; count < MAX_DISPATCH; ++count) {
        int next = htmlk_task_next(&tasks, last);
        if (next == -1) break;
        if (!htmlk_task_run(&tasks, (unsigned)next))
            fail("M4_BAD_TRANSITION\n");
        running = (unsigned)next;
        htmlk_m4_context_switch(&scheduler_sp, saved_sp[running]);
        last = running;
    }
    if (!htmlk_task_all_done(&tasks))
        fail("M4_SCHEDULER_STALLED\n");
#ifdef HTMLK_M4_TASK_NEGATIVE_TEST
    if (htmlk_task_run(&tasks, 0) ||
        htmlk_task_yield_state(&tasks, 1) ||
        htmlk_task_next(&tasks, 0) != -1)
        fail("M4_TASK_RESTART_ACCEPTED\n");
    log_text("M4_TASK_RESTART_REJECTED\n");
#endif
    log_text("M4_TASKS_DONE\n");
}
