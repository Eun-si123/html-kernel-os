#include "user_probe.h"
#include "user_pages.h"
#include "page_pool.h"
#include "frame_owner.h"
#ifdef HTMLK_M5_USER_LOADER
#include "romfs.h"
#include "user_image.h"
#endif
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

/* C1: a single bounded ring3 test, not a process loader or general VMM. */
static const uint64_t user_cs = 0x2bU, user_ss = 0x33U;
uint64_t *htmlk_m4_saved_main_rsp;
uint64_t htmlk_m4_saved_cr3;
static struct htmlk_frame_registry frames_registry;
static uint64_t frames[6];
static volatile bool syscall_seen;
static volatile bool user_exited;
#ifdef HTMLK_M5_USER_LOADER
static volatile bool user_reported;
#ifdef HTMLK_M5_INTERACTIVE_RUN
static const char *selected_app_path;
#endif
static void log_decimal(uint32_t number) {
    char digits[5];
    unsigned count = 0;
    do { digits[count++] = (char)('0' + (number % 10U)); number /= 10U; }
    while (number != 0U);
    while (count != 0U) {
        const uint8_t byte = (uint8_t)digits[--count];
#ifdef HTMLK_M5_INTERACTIVE_RUN
        htmlk_m5_console_byte(byte);
#else
        __asm__ volatile ("outb %0,%1" :: "a"(byte), "Nd"((uint16_t)0xe9));
#endif
    }
}
#endif
static uint64_t user_code_length;

struct user_irq_frame {
    uint64_t r15,r14,r13,r12,r11,r10,r9,r8;
    uint64_t rbp,rdi,rsi,rdx,rcx,rbx,rax;
    uint64_t rip,cs,rflags,rsp,ss;
};
_Static_assert(sizeof(struct user_irq_frame)==160,"ring3 syscall IRQ frame mismatch");

static void log_text(const char *s) {
    while (*s) {
#ifdef HTMLK_M5_INTERACTIVE_RUN
        htmlk_m5_console_byte((uint8_t)*s++);
#else
        __asm__ volatile ("outb %0, %1" : :
            "a"((uint8_t)*s++), "Nd"((uint16_t)0xe9));
#endif
    }
}
__attribute__((noreturn)) static void reject(const char *s) {
    __asm__ volatile ("cli" ::: "memory");
    log_text(s);
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0, %1" : :
        "a"((uint8_t)0x1aU), "Nd"((uint16_t)0xf4)); /* QEMU error 53 */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static bool canonical(uint64_t value) {
    const uint64_t top = value >> 48U;
    return top == (((value >> 47U) & 1U) ? UINT64_C(0xffff) : 0U);
}
void htmlk_m4_syscall_dispatch(void *raw_frame) {
    struct user_irq_frame *f = raw_frame;
    if (f == 0 || f->cs != user_cs || f->ss != user_ss ||
        (f->rip < HTMLK_M4_USER_BASE) ||
        f->rip >= HTMLK_M4_USER_BASE + user_code_length ||
        f->rsp <= HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE ||
        f->rsp > HTMLK_M4_USER_STACK ||
        !canonical(f->rip) || !canonical(f->rsp))
        reject("M4_BAD_RING3_SYSCALL_FRAME\n");
#ifdef HTMLK_M5_USER_LOADER
    uint64_t running_cr3;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(running_cr3));
    if (running_cr3 != frames[0] || (f->rflags & (UINT64_C(3) << 12)) != 0)
        reject("M5_C_INVALID_SYSCALL_ADDRESS_SPACE\n");
#endif
    const uint64_t id = f->rax;
    if (id == 0U && f->rdi == UINT64_C(0x1234) && !syscall_seen) {
        syscall_seen = true;
#ifdef HTMLK_M5_USER_LOADER
        log_text("M5_C_RING3_STACK_OK\n");
#else
        log_text("M4_RING3_CPL3_SYSCALL_OK\n");
#endif
        return; /* assembly iretq resumes same ring3 task */
    }
#ifdef HTMLK_M5_USER_LOADER
    if (id == 2U && syscall_seen && !user_reported && !user_exited &&
        f->rdi <= 9999U) {
        user_reported = true;
        log_text("M5_C_USER_VALUE=");
        log_decimal((uint32_t)f->rdi);
        log_text("\n");
        return;
    }
#endif
    if (id == 1U && f->rdi == 0U && syscall_seen && !user_exited
#ifdef HTMLK_M5_USER_LOADER
        && user_reported
#endif
        ) {
        user_exited = true;
#ifdef HTMLK_M5_USER_LOADER
        log_text("M5_C_RING3_EXIT_OK\n");
#else
        log_text("M4_RING3_EXIT_OK\n");
#endif
        htmlk_m4_user_return(); /* restores root CR3 and kernel call stack */
    }
    reject("M4_UNKNOWN_SYSCALL_REJECTED\n");
}

void htmlk_m4_user_probe(const struct limine_memmap_response *map,
                         const struct limine_hhdm_response *hhdm) {
    __asm__ volatile ("cli" ::: "memory");
    if (!map || !hhdm || !map->entries || map->entry_count == 0 ||
        map->entry_count > HTMLK_MAX_MEMORY_REGIONS)
        reject("M4_USER_NO_BOOT_MEMMAP\n");
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4, %0" : "=r"(cr4));
    if ((cr4 & (UINT64_C(1) << 12)) != 0
#ifdef HTMLK_M5_USER_LOADER
        || (cr4 & (UINT64_C(1) << 17)) != 0
#endif
        )
        reject("M4_USER_LA57_UNSUPPORTED\n");
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i=0; i<map->entry_count; ++i) {
        if (!map->entries[i]) reject("M4_USER_NULL_MEMMAP_ENTRY\n");
        regions[i].base = map->entries[i]->base;
        regions[i].length = map->entries[i]->length;
        regions[i].type = map->entries[i]->type;
    }
    struct htmlk_page_pool pool = {0};
    if (!htmlk_page_pool_init(regions, map->entry_count, &pool) ||
        !htmlk_frames_init(&frames_registry, &pool))
        reject("M4_USER_NO_FRAME_POOL\n");
    __asm__ volatile ("mov %%cr3, %0" : "=r"(htmlk_m4_saved_cr3));
    const uint64_t old_root = htmlk_m4_saved_cr3 & HTMLK_M4_USER_PHYS_MASK;
#ifdef HTMLK_M5_USER_LOADER
    if (old_root != htmlk_m4_saved_cr3)
        reject("M5_C_CR3_FLAGS_UNSUPPORTED\n");
#endif
    const uint64_t offset = hhdm->offset;
    if (!old_root || !offset || (offset & (HTMLK_PAGE_SIZE - 1U)) ||
        offset > UINT64_MAX - old_root - HTMLK_PAGE_SIZE)
        reject("M4_USER_BAD_CR3_HHDM\n");
    for (unsigned i=0; i<6; ++i) {
        enum htmlk_frame_owner owner =
            i<4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
        if (!htmlk_frame_claim(&frames_registry, owner, &frames[i]) ||
            frames[i] > HTMLK_M4_USER_PHYS_MASK ||
            offset > UINT64_MAX - frames[i] - HTMLK_PAGE_SIZE)
            reject("M4_USER_ALLOC_FAILED\n");
    }
    volatile uint64_t *original =
        (volatile uint64_t *)(uintptr_t)(offset + old_root);
    volatile uint64_t *root =
        (volatile uint64_t *)(uintptr_t)(offset + frames[0]);
    volatile uint64_t *pdpt =
        (volatile uint64_t *)(uintptr_t)(offset + frames[1]);
    volatile uint64_t *pd =
        (volatile uint64_t *)(uintptr_t)(offset + frames[2]);
    volatile uint64_t *pt =
        (volatile uint64_t *)(uintptr_t)(offset + frames[3]);
    volatile uint8_t *code =
        (volatile uint8_t *)(uintptr_t)(offset + frames[4]);
    volatile uint8_t *stack =
        (volatile uint8_t *)(uintptr_t)(offset + frames[5]);
    for (unsigned i=0; i<512; ++i) {
        /* Critical: inherited kernel mappings cannot carry U/S=1. */
        root[i] = original[i] & ~HTMLK_M4_USER_BIT;
    }
#ifdef HTMLK_M5_USER_LOADER
    size_t loaded = 0;
    if (!htmlk_romfs_read(&htmlk_romfs_image,
#ifdef HTMLK_M5_INTERACTIVE_RUN
                          selected_app_path,
#else
                          "/apps/hello.hke",
#endif
                          0,
                          (uint8_t *)(uintptr_t)code, HTMLK_PAGE_SIZE,
                          &loaded))
        reject("M5_C_PROGRAM_NOT_FOUND\n");
    struct htmlk_hke_program program = {0};
    if (!htmlk_hke_validate((const uint8_t *)(uintptr_t)code,
                            loaded, &program))
        reject("M5_C_IMAGE_INVALID\n");
    user_code_length = program.code_length;
    /* Shift the validated bytes left by a fixed 32-byte header.
     * The copy is overlap-safe in this direction. */
    for (unsigned i = 0; i < HTMLK_PAGE_SIZE; ++i) {
        code[i] = i < user_code_length ? code[i + HTMLK_HKE_HEADER_BYTES] : 0U;
        stack[i] = 0U;
    }
    log_text("M5_C_ROMFS_PROGRAM_LOADED\n");
#else
    const uintptr_t first = (uintptr_t)htmlk_m4_user_code_begin;
    const uintptr_t last = (uintptr_t)htmlk_m4_user_code_end;
    if (last <= first || last - first > HTMLK_PAGE_SIZE)
        reject("M4_USER_BAD_TEXT_SIZE\n");
    user_code_length = (uint64_t)(last - first);
    for (unsigned i=0; i<HTMLK_PAGE_SIZE; ++i) {
        code[i] = i<user_code_length ? htmlk_m4_user_code_begin[i] : 0U;
        stack[i] = 0;
    }
#endif
    if (!htmlk_m4_user_wire(root, pdpt, pd, pt, frames))
        reject("M4_USER_UNSAFE_PAGE_TABLE\n");
    if ((root[HTMLK_M4_USER_SLOT] & 7U) != 7U ||
        (pt[0] & 7U) != 5U || (pt[1] & 7U) != 7U)
        reject("M4_USER_PTE_PERMISSIONS_WRONG\n");
    syscall_seen = user_exited = false;
#ifdef HTMLK_M5_USER_LOADER
    user_reported = false;
    log_text("M5_C_USER_PAGES_READY\n");
#else
    log_text("M4_USER_PAGE_TABLES_READY\n");
#endif
    const uint64_t user_root = frames[0];
    __asm__ volatile ("mov %0, %%cr3" : : "r"(user_root) : "memory");
    htmlk_m4_user_enter(HTMLK_M4_USER_BASE,
                         HTMLK_M4_USER_STACK - 16U, user_cs, user_ss);
    /* Reached only via the explicit syscall-1 return path. */
    __asm__ volatile ("cli" ::: "memory");
    uint64_t restored_cr3;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(restored_cr3));
    if (!syscall_seen || !user_exited ||
#ifdef HTMLK_M5_USER_LOADER
        !user_reported ||
#endif
        restored_cr3 != htmlk_m4_saved_cr3)
        reject("M4_USER_NOT_RESTORED\n");
    for (unsigned i=0; i<6; ++i) {
        enum htmlk_frame_owner owner =
            i<4U ? HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&frames_registry,owner,frames[i]))
            reject("M4_USER_FRAME_RELEASE_FAIL\n");
    }
    if (frames_registry.live != 0)
        reject("M4_USER_FRAME_LEAK\n");
#ifdef HTMLK_M5_USER_LOADER
    log_text("M5_C_USER_FRAMES_RECLAIMED\n");
#else
    log_text("M4_RING3_MAIN_RESTORED\n");
#endif
}

#ifdef HTMLK_M5_INTERACTIVE_RUN
void htmlk_m5_user_run(const char *path,
                       const struct limine_memmap_response *map,
                       const struct limine_hhdm_response *hhdm) {
    selected_app_path = path;
    htmlk_m4_user_probe(map, hhdm);
    selected_app_path = 0;
}
#endif
