#include "user_preempt.h"
#include "user_timer_policy.h"
#include "user_pages.h"
#include "isolation_policy.h"
#include "page_pool.h"
#include "frame_owner.h"
#include "tss_ist.h"
#include "user_probe.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* One QEMU CPU, two concurrent CPL3 CR3s and isolated per-task RSP0.
 * No FPU/SIMD, FS/GS, SMP, or untrusted program loader. */
enum { D_BAD = 0, D_GOOD = 1, D_TASKS = 2, D_FRAMES = 6,
       D_KSTACK_BYTES = 16384, D_MAX_TICKS = 80 };
#define D_CANARY UINT64_C(0x91e72b3e5c00d111)
#define D_APIC_BASE 0x1bU
#define D_X2_TPR 0x808U
#define D_X2_EOI 0x80bU
#define D_X2_SVR 0x80fU
#define D_X2_LVT_TIMER 0x832U
#define D_X2_INIT_COUNT 0x838U
#define D_X2_DIVIDE 0x83eU
static uint8_t kernel_stacks[D_TASKS][D_KSTACK_BYTES]
    __attribute__((aligned(16)));
static struct htmlk_frame_registry registry;
static uint64_t phys[D_TASKS][D_FRAMES];
static uint64_t image_len[D_TASKS], hhdm, kernel_cr3;
static uint64_t *saved[D_TASKS];
static uint64_t ticks[D_TASKS], irq_total;
static unsigned current = D_TASKS;
static bool failed_bad, ready_good, exited_good;
uint64_t *htmlk_m4_saved_main_rsp;
uint64_t htmlk_m4_saved_cr3;

static void out(uint16_t port, uint8_t value) {
    __asm__ volatile ("outb %0,%1" : : "a"(value), "Nd"(port) : "memory");
}
static void log_text(const char *s) {
    while (*s) out(0xe9U, (uint8_t)*s++);
}
__attribute__((noreturn)) static void fail(const char *reason) {
    __asm__ volatile ("cli" ::: "memory");
    log_text(reason);
#ifdef HTMLK_QEMU_TEST_EXIT
    out(0xf4U, 0x1cU); /* QEMU exit 57 */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static uint64_t read_cr3(void) {
    uint64_t v;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(v));
    return v;
}
static void set_cr3(uint64_t v) {
    __asm__ volatile ("mov %0,%%cr3" : : "r"(v) : "memory");
}
static uint64_t rdmsr(uint32_t reg) {
    uint32_t lo, hi;
    __asm__ volatile ("rdmsr" : "=a"(lo), "=d"(hi) : "c"(reg));
    return ((uint64_t)hi << 32) | lo;
}
static void wrmsr(uint32_t reg, uint64_t v) {
    __asm__ volatile ("wrmsr" : : "c"(reg),
        "a"((uint32_t)v), "d"((uint32_t)(v >> 32)) : "memory");
}
static void apic_start(void) {
    uint32_t eax, ebx, ecx, edx;
    __asm__ volatile ("cli; cpuid" : "=a"(eax), "=b"(ebx),
        "=c"(ecx), "=d"(edx) : "a"(1U), "c"(0U) : "memory");
    (void)eax; (void)ebx;
    if (!(edx & (1U << 9)) || !(ecx & (1U << 21)))
        fail("M4_D_X2APIC_UNSUPPORTED\n");
    const uint64_t base = rdmsr(D_APIC_BASE);
    if (!(base & (1ULL << 11))) fail("M4_D_APIC_DISABLED\n");
    wrmsr(D_APIC_BASE, base | (1ULL << 10));
    if ((rdmsr(D_APIC_BASE) & (3ULL << 10)) != (3ULL << 10))
        fail("M4_D_X2APIC_NOT_ACTIVE\n");
    out(0x21U, 0xffU);
    out(0xa1U, 0xffU);
    wrmsr(D_X2_TPR, 0U);
    wrmsr(D_X2_SVR, 0x1ffU);
    wrmsr(D_X2_DIVIDE, 3U);
#ifdef HTMLK_M4_D_TIMER_MASK
    wrmsr(D_X2_LVT_TIMER, 0x30040U);
#else
    wrmsr(D_X2_LVT_TIMER, 0x20040U);
#endif
    wrmsr(D_X2_INIT_COUNT, 1000000U);
    log_text("M4_D_X2APIC_READY\n");
}
static void apic_stop(void) {
    wrmsr(D_X2_LVT_TIMER, 0x30040U);
    wrmsr(D_X2_INIT_COUNT, 0U);
}
static uintptr_t kbase(unsigned task) {
    return (uintptr_t)&kernel_stacks[task][0];
}
static uint64_t ktop(unsigned task) {
    return (uint64_t)(kbase(task) + D_KSTACK_BYTES);
}
static uint64_t *user_flag(unsigned task) {
    return (uint64_t *)(uintptr_t)(
        hhdm + phys[task][5] + HTMLK_PAGE_SIZE - 24U);
}
static bool good_frame(unsigned task, const struct htmlk_m4_irq_frame *f) {
    return task < D_TASKS &&
        htmlk_m4_d_frame_valid(f, kbase(task), D_KSTACK_BYTES,
                               image_len[task]) &&
        *(const uint64_t *)(uintptr_t)kbase(task) == D_CANARY;
}
static void initialize_frame(unsigned task) {
    const uintptr_t top = (uintptr_t)ktop(task);
    struct htmlk_m4_irq_frame *f =
        (struct htmlk_m4_irq_frame *)(top - sizeof(*f));
    uint64_t *p = (uint64_t *)f;
    for (unsigned i = 0; i < sizeof(*f) / sizeof(uint64_t); ++i)
        p[i] = 0;
    /* First 15 fields are actual GPRs: unique task-specific CPU sentinels. */
    for (unsigned i = 0; i < 15U; ++i)
        p[i] = (task == D_BAD ? 0x100U : 0x200U) + i;
    f->rip = HTMLK_M4_USER_BASE;
    f->rsp = HTMLK_M4_USER_STACK - 16U;
    f->cs = HTMLK_M4_ISO_USER_CS;
    f->ss = HTMLK_M4_ISO_USER_SS;
    f->rflags = 0x202U;
    *(uint64_t *)(uintptr_t)kbase(task) = D_CANARY;
    saved[task] = (uint64_t *)f;
    if (!good_frame(task, f)) fail("M4_D_INITIAL_FRAME_INVALID\n");
}
static void select_task(unsigned task) {
    if (task >= D_TASKS || !good_frame(task,
            (struct htmlk_m4_irq_frame *)saved[task]))
        fail("M4_D_SELECT_INVALID_FRAME\n");
    if (!htmlk_tss_set_rsp0(ktop(task)))
        fail("M4_D_INVALID_TSS_RSP0\n");
    current = task;
    set_cr3(phys[task][0]); /* flush stale non-global user TLB entries */
}
uint64_t *htmlk_m4_d_timer_handler(uint64_t *raw) {
    /* Negative proof: corrupt the active root, not just the owner flag. */
#ifdef HTMLK_M4_D_BAD_CR3
    if (current == D_BAD && ticks[D_BAD] == 1U)
        set_cr3(kernel_cr3);
#endif
    if (current >= D_TASKS || failed_bad ||
        read_cr3() != phys[current][0] || ++irq_total > D_MAX_TICKS)
        fail("M4_D_IRQ_BAD_CONTEXT_OR_TIMEOUT\n");
    struct htmlk_m4_irq_frame *f = (void *)raw;
    if (!good_frame(current, f))
        fail("M4_D_IRQ_FRAME_OR_PRIVILEGE_INVALID\n");
    saved[current] = raw;
    if (ticks[current] >= 3U)
        fail("M4_D_IRQ_EXCESS_TICKS_NO_FAULT\n");
    const unsigned previous = current;
    const uint8_t number = (uint8_t)('0' + ticks[previous]);
    log_text(previous == D_BAD ? "M4_D_A_TICK_" : "M4_D_B_TICK_");
    out(0xe9U, number);
    out(0xe9U, '\n');
    ++ticks[previous];
#ifdef HTMLK_M4_D_REVOKE_B_CODE
    /* B ran already: revoke B code PTE, then CR3 switch must flush its TLB. */
    if (previous == D_BAD && ticks[D_BAD] == 2U) {
        volatile uint64_t *bpt = (void *)(uintptr_t)(hhdm + phys[D_GOOD][3]);
        bpt[0] &= ~1ULL;
    }
#endif
    if (previous == D_BAD && ticks[D_BAD] == 3U)
        *user_flag(D_BAD) = 1U; /* A faults on next scheduled timeslice */
    const unsigned next = previous ^ 1U;
    if (!good_frame(next, (struct htmlk_m4_irq_frame *)saved[next]))
        fail("M4_D_NEXT_SAVED_FRAME_INVALID\n");
    select_task(next);
    wrmsr(D_X2_EOI, 0U);
    return saved[next];
}
bool htmlk_m4_d_accept_fault(uint64_t rip, uint64_t cs, uint64_t rsp,
                              uint64_t ss, uint64_t error, uint64_t cr2) {
    if (current != D_BAD || failed_bad ||
        ticks[D_BAD] != 3U || ticks[D_GOOD] != 3U ||
        *user_flag(D_BAD) != 1U ||
        !good_frame(D_GOOD, (struct htmlk_m4_irq_frame *)saved[D_GOOD]))
        return false;
    if (!htmlk_m4_iso_fault_valid(14U, 14U, D_BAD, rip, cs, rsp, ss,
            error, cr2, read_cr3(), phys[D_BAD][0], image_len[D_BAD],
            5U, HTMLK_M4_ISO_BAD_KERNEL_ADDRESS))
        return false;
    failed_bad = true;
    log_text("M4_D_A_PF_ERROR_5\n");
    return true;
}
static void release_task(unsigned task) {
    if (task >= D_TASKS || read_cr3() != kernel_cr3)
        fail("M4_D_RELEASE_WRONG_CR3\n");
    for (unsigned i = 0; i < D_FRAMES; ++i)
        if (!htmlk_frame_release(&registry,
                i < 4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA,
                phys[task][i]))
            fail("M4_D_FRAME_OWNER_INVALID\n");
}
__attribute__((noreturn)) void htmlk_m4_d_recover_fault(void) {
    __asm__ volatile ("cli" ::: "memory");
    if (!failed_bad || current != D_BAD)
        fail("M4_D_FAULT_RECOVERY_UNARMED\n");
    set_cr3(kernel_cr3);
    current = D_TASKS; /* disarm A before frame reclamation */
    release_task(D_BAD);
    if (registry.live != 6U) fail("M4_D_A_RECLAIM_LEAK\n");
    if (htmlk_frame_release(&registry, HTMLK_FRAME_TABLE, phys[D_BAD][0]))
        fail("M4_D_DOUBLE_RELEASE_ALLOWED\n");
    log_text("M4_D_A_RECLAIMED\n");
    if (*user_flag(D_GOOD) != 0U)
        fail("M4_D_USER_STACK_CROSS_TALK\n");
    *user_flag(D_GOOD) = 1U;
    select_task(D_GOOD);
    htmlk_m4_d_resume_user(saved[D_GOOD]); /* leave IST2 on clean B stack */
    __builtin_unreachable();
}
void htmlk_m4_syscall_dispatch(void *stack) {
    const struct htmlk_m4_irq_frame *f = stack;
    if (current != D_GOOD || !failed_bad || !good_frame(D_GOOD, f) ||
        read_cr3() != phys[D_GOOD][0] ||
        ticks[D_BAD] != 3U || ticks[D_GOOD] != 3U ||
        *user_flag(D_GOOD) != 1U)
        fail("M4_D_BAD_USER_SYSCALL_FRAME\n");
    if (f->rax == 0U && f->rdi == 0x1234U && !ready_good) {
        ready_good = true;
        log_text("M4_D_B_SYSCALL_OK\n");
        return;
    }
    if (f->rax == 1U && f->rdi == 0U && ready_good && !exited_good) {
        exited_good = true;
        log_text("M4_D_B_EXIT_OK\n");
        htmlk_m4_user_return();
    }
    fail("M4_D_UNKNOWN_SYSCALL_REJECTED\n");
}
static void initialize_user_pages(unsigned task, const uint8_t *start,
                                  const uint8_t *end,
                                  volatile const uint64_t *original) {
    if ((uintptr_t)end <= (uintptr_t)start ||
        (uintptr_t)end - (uintptr_t)start > HTMLK_PAGE_SIZE)
        fail("M4_D_BAD_IMAGE_LENGTH\n");
    image_len[task] = (uintptr_t)end - (uintptr_t)start;
    volatile uint64_t *root = (void *)(uintptr_t)(hhdm + phys[task][0]);
    volatile uint64_t *pdpt = (void *)(uintptr_t)(hhdm + phys[task][1]);
    volatile uint64_t *pd = (void *)(uintptr_t)(hhdm + phys[task][2]);
    volatile uint64_t *pt = (void *)(uintptr_t)(hhdm + phys[task][3]);
    volatile uint8_t *code = (void *)(uintptr_t)(hhdm + phys[task][4]);
    volatile uint8_t *stack = (void *)(uintptr_t)(hhdm + phys[task][5]);
    for (unsigned i = 0; i < 512U; ++i)
        root[i] = original[i] & ~HTMLK_M4_USER_BIT;
    for (unsigned i = 0; i < HTMLK_PAGE_SIZE; ++i) {
        code[i] = i < image_len[task] ? start[i] : 0U;
        stack[i] = 0U;
    }
    if (!htmlk_m4_user_wire(root, pdpt, pd, pt, phys[task]) ||
        (root[HTMLK_M4_USER_SLOT] & 7U) != 7U ||
        (pt[0] & 7U) != 5U || (pt[1] & 7U) != 7U)
        fail("M4_D_PAGE_PERMISSIONS_INVALID\n");
    initialize_frame(task);
}
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *map,
                                 const struct limine_hhdm_response *hhdm_response) {
    __asm__ volatile ("cli" ::: "memory");
    if (!map || !map->entries || !map->entry_count ||
        map->entry_count > HTMLK_MAX_MEMORY_REGIONS || !hhdm_response)
        fail("M4_D_INVALID_LIMINE_MEMORY\n");
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4,%0" : "=r"(cr4));
    if (cr4 & ((UINT64_C(1) << 12) | (UINT64_C(1) << 17)))
        fail("M4_D_LA57_PCID_UNSUPPORTED\n");
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i = 0; i < map->entry_count; ++i) {
        if (!map->entries[i]) fail("M4_D_NULL_REGION\n");
        regions[i].base = map->entries[i]->base;
        regions[i].length = map->entries[i]->length;
        regions[i].type = map->entries[i]->type;
    }
    struct htmlk_page_pool pool = {0};
    if (!htmlk_page_pool_init(regions, map->entry_count, &pool) ||
        !htmlk_frames_init(&registry, &pool))
        fail("M4_D_OUT_OF_FRAMES\n");
    kernel_cr3 = read_cr3();
    htmlk_m4_saved_cr3 = kernel_cr3;
    hhdm = hhdm_response->offset;
    if (!kernel_cr3 || (kernel_cr3 & ~HTMLK_M4_ISO_CR3_MASK) != 0 ||
        !hhdm || (hhdm & (HTMLK_PAGE_SIZE - 1U)) != 0 ||
        hhdm > UINT64_MAX - kernel_cr3 - HTMLK_PAGE_SIZE)
        fail("M4_D_INVALID_ORIGINAL_CR3\n");
    for (unsigned task = 0; task < D_TASKS; ++task)
        for (unsigned i = 0; i < D_FRAMES; ++i)
            if (!htmlk_frame_claim(&registry,
                    i < 4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA,
                    &phys[task][i]) ||
                phys[task][i] > HTMLK_M4_USER_PHYS_MASK ||
                hhdm > UINT64_MAX - phys[task][i] - HTMLK_PAGE_SIZE)
                fail("M4_D_OUT_OF_OWNED_FRAMES\n");
    if (registry.live != 12U || phys[D_BAD][0] == phys[D_GOOD][0] ||
        phys[D_BAD][5] == phys[D_GOOD][5])
        fail("M4_D_NONINDEPENDENT_ROOTS\n");
    volatile const uint64_t *original =
        (void *)(uintptr_t)(hhdm + kernel_cr3);
    initialize_user_pages(D_BAD, htmlk_m4_d_bad_begin, htmlk_m4_d_bad_end, original);
    initialize_user_pages(D_GOOD, htmlk_m4_d_good_begin, htmlk_m4_d_good_end, original);
#ifdef HTMLK_M4_D_CORRUPT_GPR
    ((struct htmlk_m4_irq_frame *)saved[D_BAD])->r15 ^= 1U;
#endif
#ifdef HTMLK_M4_D_FORGED_FRAME
    struct htmlk_m4_irq_frame *f = (void *)saved[D_BAD];
    f->cs = 0x08U;
    if (!good_frame(D_BAD, f))
        fail("M4_D_FORGED_CPL0_REJECTED\n");
    fail("M4_D_FORGED_CPL0_ACCEPTED\n");
#endif
    log_text("M4_D_TWO_CR3_READY\n");
    apic_start();
    select_task(D_BAD);
    htmlk_m4_d_enter_first(saved[D_BAD]);
    __asm__ volatile ("cli" ::: "memory");
    if (read_cr3() != kernel_cr3 || !failed_bad || !ready_good ||
        !exited_good || ticks[D_BAD] != 3U || ticks[D_GOOD] != 3U)
        fail("M4_D_BAD_MAIN_RETURN\n");
    apic_stop();
    release_task(D_GOOD);
    if (registry.live != 0)
        fail("M4_D_FRAME_LEAK\n");
    log_text("M4_D_NO_FRAME_LEAK\n");
}
