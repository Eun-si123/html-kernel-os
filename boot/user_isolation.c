#include "user_isolation.h"
#include "user_probe.h"
#include "user_pages.h"
#include "isolation_policy.h"
#include "page_pool.h"
#include "frame_owner.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* C2: two distinct bounded user CR3s, sequential CPU execution.
 * IRQ preemption/parallel user scheduling are explicitly NOT included.
 */
enum { BAD = 0, SURVIVOR = 1, TASKS = 2, OWNED = 6 };
static struct htmlk_frame_registry registry;
static uint64_t phys[TASKS][OWNED];
static uint64_t hhdm, original_cr3, image_bytes[TASKS];
static unsigned active_task = TASKS;
static bool ready[TASKS], exited[TASKS], faulted[TASKS];
uint64_t *htmlk_m4_saved_main_rsp;
uint64_t htmlk_m4_saved_cr3;

struct iso_irq_frame {
    uint64_t r15, r14, r13, r12, r11, r10, r9, r8;
    uint64_t rbp, rdi, rsi, rdx, rcx, rbx, rax;
    uint64_t rip, cs, rflags, rsp, ss;
};
_Static_assert(sizeof(struct iso_irq_frame) == 160,
               "x86-64 user syscall stack frame layout");

static void log_text(const char *s) {
    while (*s) {
        __asm__ volatile ("outb %0, %1" : :
            "a"((uint8_t)*s++), "Nd"((uint16_t)0xe9));
    }
}
__attribute__((noreturn)) static void fail(const char *s) {
    __asm__ volatile ("cli" ::: "memory");
    log_text(s);
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0, %1" : :
        "a"((uint8_t)0x1bU), "Nd"((uint16_t)0xf4)); /* 55 */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static uint64_t current_cr3(void) {
    uint64_t v;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(v));
    return v;
}
static bool on_expected_cr3(unsigned task) {
    return task < TASKS && current_cr3() == phys[task][0];
}
static uint64_t stack_value(unsigned task) {
    volatile uint64_t *p = (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][5] + HTMLK_PAGE_SIZE - 24U);
    return *p;
}
static bool valid_syscall_frame(const struct iso_irq_frame *f) {
    return f && active_task < TASKS && on_expected_cr3(active_task) &&
        f->cs == HTMLK_M4_ISO_USER_CS &&
        f->ss == HTMLK_M4_ISO_USER_SS &&
        f->rip >= HTMLK_M4_USER_BASE &&
        f->rip - HTMLK_M4_USER_BASE < image_bytes[active_task] &&
        f->rsp > HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE &&
        f->rsp <= HTMLK_M4_USER_STACK;
}
void htmlk_m4_syscall_dispatch(void *stack) {
    struct iso_irq_frame *f = stack;
    if (!valid_syscall_frame(f))
        fail("M4_ISO_BAD_SYSCALL_FRAME\n");
    if (active_task == BAD && f->rax == 2U &&
        f->rdi == UINT64_C(0xa55a) && !ready[BAD] &&
        stack_value(BAD) == UINT64_C(0x1111)) {
        ready[BAD] = true;
        log_text("M4_ISO_A_CPL3_READY\n");
        return;
    }
    if (active_task == SURVIVOR && f->rax == 0U &&
        f->rdi == UINT64_C(0x1234) && !ready[SURVIVOR] &&
        faulted[BAD] && stack_value(SURVIVOR) == UINT64_C(0x2222)) {
        ready[SURVIVOR] = true;
        log_text("M4_ISO_B_CPL3_SYSCALL_OK\n");
        return;
    }
    if (active_task == SURVIVOR && f->rax == 1U &&
        f->rdi == 0U && ready[SURVIVOR] && !exited[SURVIVOR]) {
        exited[SURVIVOR] = true;
        log_text("M4_ISO_B_EXIT_OK\n");
        htmlk_m4_user_return();
    }
    fail("M4_ISO_UNSUPPORTED_SYSCALL\n");
}
bool htmlk_m4_iso_accept_fault(unsigned vector, uint64_t rip, uint64_t cs,
                               uint64_t rsp, uint64_t ss, uint64_t error,
                               uint64_t cr2) {
    if (active_task != BAD || !ready[BAD] || faulted[BAD] ||
        !htmlk_m4_iso_fault_valid(vector,
#ifdef HTMLK_M4_ISO_GP
            13U,
#else
            14U,
#endif
            active_task, rip, cs, rsp, ss, error, cr2,
            current_cr3(), phys[BAD][0], image_bytes[BAD],
#ifdef HTMLK_M4_ISO_GP
            0U, 0U))
#elif defined(HTMLK_M4_ISO_RO)
            7U, HTMLK_M4_ISO_USER_START))
#else
            5U, HTMLK_M4_ISO_BAD_KERNEL_ADDRESS))
#endif
        return false;
    faulted[BAD] = true;
#ifdef HTMLK_M4_ISO_GP
    log_text("M4_ISO_A_GP_ERROR_0\n");
#elif defined(HTMLK_M4_ISO_RO)
    log_text("M4_ISO_A_PF_ERROR_7\n");
#else
    log_text("M4_ISO_A_PF_ERROR_5\n");
#endif
    return true; /* exception handler abandons user context on trusted stack */
}
static void init_user_task(unsigned task,
                           const unsigned char *start,
                           const unsigned char *end,
                           volatile uint64_t *original) {
    const uintptr_t begin = (uintptr_t)start;
    const uintptr_t finish = (uintptr_t)end;
    if (finish <= begin || finish - begin > HTMLK_PAGE_SIZE)
        fail("M4_ISO_IMAGE_SIZE_INVALID\n");
    image_bytes[task] = (uint64_t)(finish - begin);
    volatile uint64_t *root = (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][0]);
    volatile uint64_t *pdpt = (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][1]);
    volatile uint64_t *pd = (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][2]);
    volatile uint64_t *pt = (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][3]);
    volatile uint8_t *code = (volatile uint8_t *)(uintptr_t)(
        hhdm + phys[task][4]);
    volatile uint8_t *stack = (volatile uint8_t *)(uintptr_t)(
        hhdm + phys[task][5]);
    for (unsigned i = 0; i < 512; ++i) {
        root[i] = original[i] & ~HTMLK_M4_USER_BIT; /* inherited kernel = ring0 */
    }
    for (unsigned i = 0; i < HTMLK_PAGE_SIZE; ++i) {
        code[i] = i < image_bytes[task] ? start[i] : 0U;
        stack[i] = 0;
    }
    if (!htmlk_m4_user_wire(root, pdpt, pd, pt, phys[task]) ||
        (root[HTMLK_M4_USER_SLOT] & 7U) != 7U ||
        (pt[0] & 7U) != 5U || (pt[1] & 7U) != 7U)
        fail("M4_ISO_BAD_USER_PAGE_TABLES\n");
}
static void release_task(unsigned task) {
    if (current_cr3() != original_cr3 || task >= TASKS)
        fail("M4_ISO_RELEASE_ON_USER_CR3\n");
    for (unsigned i = 0; i < OWNED; ++i) {
        const enum htmlk_frame_owner owner =
            i < 4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&registry, owner, phys[task][i]))
            fail("M4_ISO_WRONG_OWNER_OR_DOUBLE_FREE\n");
    }
}
void htmlk_m4_user_isolation_probe(const struct limine_memmap_response *map,
                                  const struct limine_hhdm_response *hhdm_response) {
    __asm__ volatile ("cli" ::: "memory");
    if (!map || !map->entries || !hhdm_response ||
        !map->entry_count || map->entry_count > HTMLK_MAX_MEMORY_REGIONS)
        fail("M4_ISO_INVALID_BOOT_MAP\n");
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4,%0" : "=r"(cr4));
    if ((cr4 & ((UINT64_C(1) << 12) | (UINT64_C(1) << 17))) != 0)
        fail("M4_ISO_LA57_OR_PCID_UNSUPPORTED\n");
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i = 0; i < map->entry_count; ++i) {
        if (!map->entries[i]) fail("M4_ISO_NULL_BOOT_REGION\n");
        regions[i].base = map->entries[i]->base;
        regions[i].length = map->entries[i]->length;
        regions[i].type = map->entries[i]->type;
    }
    struct htmlk_page_pool pool = {0};
    if (!htmlk_page_pool_init(regions, map->entry_count, &pool) ||
        !htmlk_frames_init(&registry, &pool))
        fail("M4_ISO_NO_USABLE_FRAME_POOL\n");
    original_cr3 = current_cr3();
    htmlk_m4_saved_cr3 = original_cr3;
    hhdm = hhdm_response->offset;
    if ((original_cr3 & ~HTMLK_M4_ISO_CR3_MASK) != 0 ||
        (original_cr3 & HTMLK_M4_ISO_CR3_MASK) == 0 ||
        hhdm == 0 || (hhdm & (HTMLK_PAGE_SIZE - 1U)) ||
        hhdm > UINT64_MAX - (original_cr3 & HTMLK_M4_ISO_CR3_MASK) - HTMLK_PAGE_SIZE)
        fail("M4_ISO_BAD_KERNEL_CR3_HHDM\n");
    for (unsigned task = 0; task < TASKS; ++task) {
        for (unsigned i = 0; i < OWNED; ++i) {
            const enum htmlk_frame_owner owner =
                i < 4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
            if (!htmlk_frame_claim(&registry, owner, &phys[task][i]) ||
                phys[task][i] > HTMLK_M4_USER_PHYS_MASK ||
                hhdm > UINT64_MAX - phys[task][i] - HTMLK_PAGE_SIZE)
                fail("M4_ISO_OUT_OF_OWNED_FRAMES\n");
        }
    }
    if (registry.live != 12 || phys[BAD][0] == phys[SURVIVOR][0] ||
        phys[BAD][5] == phys[SURVIVOR][5])
        fail("M4_ISO_SHARED_PAGE_OWNERSHIP\n");
    volatile uint64_t *original = (volatile uint64_t *)(uintptr_t)(
        hhdm + (original_cr3 & HTMLK_M4_ISO_CR3_MASK));
    init_user_task(BAD, htmlk_m4_iso_bad_begin, htmlk_m4_iso_bad_end, original);
    init_user_task(SURVIVOR, htmlk_m4_iso_good_begin, htmlk_m4_iso_good_end, original);
#ifdef HTMLK_M4_ISO_FORGED_FRAME
    if (htmlk_m4_iso_fault_valid(14U, 14U, 0U,
        HTMLK_M4_ISO_USER_START, 0x08U,
        HTMLK_M4_ISO_USER_STACK - 16U, HTMLK_M4_ISO_USER_SS,
        5U, HTMLK_M4_ISO_BAD_KERNEL_ADDRESS, phys[BAD][0],
        phys[BAD][0], image_bytes[BAD],
        5U, HTMLK_M4_ISO_BAD_KERNEL_ADDRESS))
        fail("M4_ISO_FORGED_KERNEL_CONTEXT_ACCEPTED\n");
    fail("M4_ISO_FORGED_KERNEL_CONTEXT_REJECTED\n");
#endif
    log_text("M4_ISO_TWO_CR3_READY\n");
    active_task = BAD;
    __asm__ volatile ("mov %0,%%cr3" : : "r"(phys[BAD][0]) : "memory");
    htmlk_m4_user_enter(HTMLK_M4_USER_BASE, HTMLK_M4_USER_STACK - 16U,
                         HTMLK_M4_ISO_USER_CS, HTMLK_M4_ISO_USER_SS);
    __asm__ volatile ("cli" ::: "memory");
    if (current_cr3() != original_cr3 || !faulted[BAD] ||
        !ready[BAD] || exited[BAD] || ready[SURVIVOR] ||
        stack_value(BAD) != UINT64_C(0x1111) ||
        stack_value(SURVIVOR) != 0)
        fail("M4_ISO_A_NOT_CONTAINED\n");
    active_task = TASKS; /* prevent stale user A fault acceptance */
    release_task(BAD);
    if (registry.live != 6)
        fail("M4_ISO_A_FRAME_LEAK\n");
    log_text("M4_ISO_A_RECLAIMED\n");
    active_task = SURVIVOR;
    __asm__ volatile ("mov %0,%%cr3" : : "r"(phys[SURVIVOR][0]) : "memory");
    htmlk_m4_user_enter(HTMLK_M4_USER_BASE, HTMLK_M4_USER_STACK - 16U,
                         HTMLK_M4_ISO_USER_CS, HTMLK_M4_ISO_USER_SS);
    __asm__ volatile ("cli" ::: "memory");
    if (current_cr3() != original_cr3 || !ready[SURVIVOR] ||
        !exited[SURVIVOR] || stack_value(SURVIVOR) != UINT64_C(0x2222))
        fail("M4_ISO_B_BAD_RESTORATION\n");
    active_task = TASKS;
    release_task(SURVIVOR);
    if (registry.live != 0)
        fail("M4_ISO_SURVIVOR_FRAME_LEAK\n");
    log_text("M4_ISO_NO_FRAME_LEAK\n");
}
