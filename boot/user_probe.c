#include "user_probe.h"
#include "user_pages.h"
#include "page_pool.h"
#include "frame_owner.h"
#ifdef HTMLK_M5_USER_LOADER
#include "romfs.h"
#include "user_image.h"
#ifdef HTMLK_M5_USER_TEXT
#include "user_text_policy.h"
#endif
#ifdef HTMLK_M5_USER_FAULT_RECOVER
#include "user_fault_policy.h"
#include "user_syscall_policy.h"
#include "tss_ist.h"
#ifdef HTMLK_M5_USER_TIMEOUT
#include "user_timeout.h"
#include "user_timeout_frame.h"
#endif
#endif
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
/* Single active M5 app. The kernel and all its interrupt handlers are
 * compiled -mgeneral-regs-only. Preserve the supervisor's legacy x87
 * context and give each fresh task a clean one when x87 is available.
 * No CR0/CR4 feature enable, SSE/XSAVE state or concurrent task claim. */
static struct { uint8_t bytes[108]; } saved_x87 __attribute__((aligned(16)));
static bool x87_saved;
static void user_x87_begin(void) {
    uint64_t cr0;
    __asm__ volatile("mov %%cr0,%0" : "=r"(cr0));
    x87_saved = (cr0 & (UINT64_C(1)<<2 | UINT64_C(1)<<3)) == 0;
    if (!x87_saved) return; /* EM/TS: do not execute disabled x87 */
    __asm__ volatile(
        "fnsave %0\n\t"
        /* FNSAVE initializes tags, not physical register contents.
         * Fill all eight physical registers, then mark all empty again. */
        "fldz; fldz; fldz; fldz; fldz; fldz; fldz; fldz; fninit"
        : "=m"(saved_x87) : : "memory");
}
static void user_x87_end(void) {
    if (!x87_saved) return;
    /* FRSTOR replaces the entire legacy state, including control word,
     * status, tags and physical register contents. Clear pending user
     * exceptions with the non-waiting FNCLEX before FRSTOR. */
    __asm__ volatile("fnclex; frstor %0" : : "m"(saved_x87) : "memory");
    x87_saved = false;
}

#ifdef HTMLK_M5_USER_EXIT_STATUS
/* Only HTML-derived opt-in apps may submit a bounded 8-bit exit status. */
static volatile uint8_t user_exit_code;
#endif
#ifdef HTMLK_M5_USER_MULTI_REPORT
/* Actual per-task syscall budget, independent of source-level loop estimates.
 * Enforced even if a crafted executable bypasses the shared HTML compiler. */
enum { HTMLK_M5_USER_REPORT_LIMIT = 8 };
static volatile unsigned user_report_count;
#endif
#ifdef HTMLK_M5_INTERACTIVE_RUN
static const char *selected_app_path;
#ifdef HTMLK_M5_USER_FAULT_RECOVER
static volatile bool user_faulted;
static volatile bool user_bad_syscall;
#ifdef HTMLK_M5_USER_TIMEOUT
static volatile bool user_timed_out;
#endif
#endif
#endif
/* Worst-case uint64_t decimal is 20 bytes. The syscall count remains
 * independently capped at 8 for HTML-compiled user apps. */
static void log_decimal(uint64_t number) {
    char digits[20];
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
#ifdef HTMLK_M5_USER_TEXT
static void user_text_emit_byte(uint8_t byte) {
#ifdef HTMLK_M5_INTERACTIVE_RUN
    htmlk_m5_console_byte(byte);
#else
    __asm__ volatile("outb %0,%1" :: "a"(byte), "Nd"((uint16_t)0xe9));
#endif
}
#endif

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
/* The actual CPL3 syscall *and* x2APIC IRQ use the same 160-byte
 * 15-GPR + five-word CPU frame, both on trusted TSS.RSP0. A task can
 * corrupt its saved user RIP/RSP with ordinary register instructions;
 * do not trust or dereference either field while deciding whose fault it is.
 * Callers MUST read saved CS first: a CPL0-origin CPU frame is shorter. */
#ifdef HTMLK_M5_USER_FAULT_RECOVER
static bool htmlk_m5_owned_cpu_entry(uintptr_t frame_address,
                                      uint64_t cs,uint64_t ss,uint64_t flags) {
    uint64_t active_root;
    __asm__ volatile("mov %%cr3,%0":"=r"(active_root));
    const struct htmlk_m5_syscall_provenance ctx = {
        .frame_address=(uint64_t)frame_address,
        .tss_rsp0=htmlk_tss_rsp0(),
        .cs=cs,.ss=ss,.rflags=flags,
        .active_cr3=active_root,.owned_cr3=frames[0],
        .saved_cr3=htmlk_m4_saved_cr3,
        .saved_main_rsp=(uint64_t)(uintptr_t)htmlk_m4_saved_main_rsp,
        .live_frames=frames_registry.live,
        .has_active_app=selected_app_path!=0,
        .already_terminated=user_faulted || user_bad_syscall || user_exited
#ifdef HTMLK_M5_USER_TIMEOUT
            || user_timed_out
#endif
    };
    return htmlk_m5_bad_syscall_frame_is_owned(&ctx);
}
#endif
__attribute__((noreturn))
static void invalid_syscall_frame(struct user_irq_frame *f,const char *message) {
#ifdef HTMLK_M5_USER_FAULT_RECOVER
    if (f && f->cs==user_cs &&
        htmlk_m5_owned_cpu_entry((uintptr_t)f,f->cs,f->ss,f->rflags)) {
        user_bad_syscall=true;
        log_text("M5_E_USER_BAD_SYSCALL_FRAME\n");
        htmlk_m4_user_return();
    }
#else
    (void)f;
#endif
    reject(message);
}

void htmlk_m4_syscall_dispatch(void *raw_frame) {
    struct user_irq_frame *f = raw_frame;
    /* INT 0x80 saves the *next* user RIP, exactly like a trap. A syscall
     * placed at the final instruction therefore saves RIP == code end.
     * Only the guarded M5 shell may handle that boundary; legacy modes
     * still fail-stop on RIP outside the executable's strict interval. */
#ifdef HTMLK_M5_USER_FAULT_RECOVER
    const bool at_user_code_end = f &&
        f->rip == HTMLK_M4_USER_BASE + user_code_length;
#else
    const bool at_user_code_end = false;
#endif
    if (f == 0 || f->cs != user_cs || f->ss != user_ss ||
        (f->rip < HTMLK_M4_USER_BASE) ||
        (f->rip >= HTMLK_M4_USER_BASE + user_code_length &&
         !at_user_code_end) ||
        f->rsp <= HTMLK_M4_USER_BASE + HTMLK_PAGE_SIZE ||
        f->rsp > HTMLK_M4_USER_STACK ||
        !canonical(f->rip) || !canonical(f->rsp))
        invalid_syscall_frame(f,"M4_BAD_RING3_SYSCALL_FRAME\n");
#ifdef HTMLK_M5_USER_LOADER
    uint64_t running_cr3;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(running_cr3));
    if (running_cr3 != frames[0] || (f->rflags & (UINT64_C(3) << 12)) != 0)
        invalid_syscall_frame(f,"M5_C_INVALID_SYSCALL_ADDRESS_SPACE\n");
#endif
    const uint64_t id = f->rax;
#ifdef HTMLK_M5_USER_FAULT_RECOVER
    /* Resuming an ordinary (non-exit) syscall at RIP == code end would
     * execute bytes outside the verified HKEX image and could turn a
     * legitimate CPL3 protocol error into a fatal kernel exception.
     * A valid terminating syscall may end at code end: it never IRETs. */
    if (at_user_code_end &&
        !(id == 1U &&
#ifdef HTMLK_M5_USER_EXIT_STATUS
          f->rdi <= UINT64_C(255) &&
#else
          f->rdi == 0U &&
#endif
          syscall_seen && user_reported && !user_exited)) {
        if (selected_app_path && frames_registry.live == 6U &&
            !user_faulted && !user_bad_syscall && !user_exited &&
#ifdef HTMLK_M5_USER_TIMEOUT
            !user_timed_out &&
#endif
            htmlk_m4_saved_main_rsp && htmlk_m4_saved_cr3 != frames[0]) {
            user_bad_syscall = true;
            log_text("M5_E_USER_EOF_SYSCALL_REJECTED\n");
            htmlk_m4_user_return();
        }
        reject("M4_BAD_RING3_SYSCALL_FRAME\n");
    }
#endif
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
    if ((id == 2U
#ifdef HTMLK_M5_USER_I64_OUTPUT
         || id == 4U
#endif
         ) && syscall_seen && !user_exited &&
#ifndef HTMLK_M5_USER_U64_OUTPUT
        f->rdi <= 9999U &&
#endif
#ifdef HTMLK_M5_USER_MULTI_REPORT
        user_report_count < HTMLK_M5_USER_REPORT_LIMIT
#else
        !user_reported
#endif
        ) {
        user_reported = true;
#ifdef HTMLK_M5_USER_MULTI_REPORT
        ++user_report_count;
#endif
        log_text("M5_C_USER_VALUE=");
#ifdef HTMLK_M5_USER_I64_OUTPUT
        if (id == 4U && (f->rdi & (UINT64_C(1) << 63))) {
            log_text("-");
            log_decimal(UINT64_C(0) - f->rdi);
        } else
#endif
            log_decimal(f->rdi);
        log_text("\n");
        return;
    }
#ifdef HTMLK_M5_USER_TEXT
    if (id == 3U && syscall_seen && !user_exited &&
#ifdef HTMLK_M5_USER_MULTI_REPORT
        user_report_count < HTMLK_M5_USER_REPORT_LIMIT &&
#else
        !user_reported &&
#endif
        htmlk_m5_user_text_range(f->rdi, f->rsi, user_code_length)) {
        const volatile uint8_t *text = (const volatile uint8_t *)(uintptr_t)f->rdi;
        /* Validate *every byte* before printing, no partial prompt injection. */
        bool printable = text[f->rsi-1U] == (uint8_t)'\n';
        for (uint64_t i=0; printable && i+1U<f->rsi; ++i) {
            const uint8_t byte = text[i];
            if (byte < 32U || byte > 126U) printable=false;
        }
        if (printable) {
            user_reported = true;
#ifdef HTMLK_M5_USER_MULTI_REPORT
            ++user_report_count;
#endif
            log_text("M5_F2_USER_TEXT=");
            for (uint64_t i=0; i<f->rsi; ++i) user_text_emit_byte(text[i]);
            return;
        }
    }
#endif
#endif
    if (id == 1U &&
#ifdef HTMLK_M5_USER_EXIT_STATUS
        f->rdi <= UINT64_C(255) &&
#else
        f->rdi == 0U &&
#endif
        syscall_seen && !user_exited
#ifdef HTMLK_M5_USER_LOADER
        && user_reported
#endif
        ) {
        user_exited = true;
#ifdef HTMLK_M5_USER_EXIT_STATUS
        user_exit_code = (uint8_t)f->rdi;
#endif
#ifdef HTMLK_M5_USER_LOADER
        log_text("M5_C_RING3_EXIT_OK\n");
#else
        log_text("M4_RING3_EXIT_OK\n");
#endif
        htmlk_m4_user_return(); /* restores root CR3 and kernel call stack */
    }
#ifdef HTMLK_M5_USER_FAULT_RECOVER
    /* Unknown/invalid userspace syscall is a process protocol error,
     * not a reason to take down the entire native UART shell. The checked
     * active CR3 and CPL3 frame above are mandatory before this path.
     * M4-C1/M5-C1 legacy fail-stop oracles are intentionally unchanged. */
    if (selected_app_path && frames_registry.live == 6U &&
        !user_faulted && !user_bad_syscall && !user_exited &&
        htmlk_m4_saved_main_rsp && htmlk_m4_saved_cr3 != frames[0]) {
        user_bad_syscall = true;
        log_text("M5_E_USER_BAD_SYSCALL\n");
        htmlk_m4_user_return();
    }
#endif
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
#ifdef HTMLK_M5_USER_EXIT_STATUS
    user_exit_code = 0U;
#endif
#ifdef HTMLK_M5_USER_MULTI_REPORT
    user_report_count = 0U;
#endif
#ifdef HTMLK_M5_USER_FAULT_RECOVER
    user_faulted = false;
    user_bad_syscall = false;
#ifdef HTMLK_M5_USER_TIMEOUT
    user_timed_out = false;
#endif
#endif
    log_text("M5_C_USER_PAGES_READY\n");
#else
    log_text("M4_USER_PAGE_TABLES_READY\n");
#endif
#ifdef HTMLK_M5_USER_TIMEOUT
    htmlk_m5_timeout_start();
#endif
#ifdef HTMLK_M5_USER_LOADER
    user_x87_begin();
#endif
    const uint64_t user_root = frames[0];
    __asm__ volatile ("mov %0, %%cr3" : : "r"(user_root) : "memory");
    htmlk_m4_user_enter(HTMLK_M4_USER_BASE,
                         HTMLK_M4_USER_STACK - 16U, user_cs, user_ss);
    /* All exit/fault/timeout paths restore the trusted kernel stack. */
    __asm__ volatile ("cli" ::: "memory");
#ifdef HTMLK_M5_USER_LOADER
    user_x87_end();
#endif
#ifdef HTMLK_M5_USER_TIMEOUT
    htmlk_m5_timeout_stop();
#endif
    uint64_t restored_cr3;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(restored_cr3));
    if (
#ifdef HTMLK_M5_USER_FAULT_RECOVER
        (user_faulted && user_bad_syscall) ||
#ifdef HTMLK_M5_USER_TIMEOUT
        (user_timed_out && (user_faulted || user_bad_syscall)) ||
#endif
        (!user_faulted && !user_bad_syscall
#ifdef HTMLK_M5_USER_TIMEOUT
         && !user_timed_out
#endif
         && (!syscall_seen || !user_exited || !user_reported)) ||
        ((user_faulted || user_bad_syscall
#ifdef HTMLK_M5_USER_TIMEOUT
          || user_timed_out
#endif
          ) && user_exited) ||
#else
        !syscall_seen || !user_exited ||
#ifdef HTMLK_M5_USER_LOADER
        !user_reported ||
#endif
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
#ifdef HTMLK_M5_USER_FAULT_RECOVER
#ifdef HTMLK_M5_USER_TIMEOUT
    if (user_timed_out) log_text("M5_E2_TIMEOUT_FRAMES_RECLAIMED\n");
    else
#endif
    if (user_faulted) log_text("M5_E_FAULT_FRAMES_RECLAIMED\n");
    else if (user_bad_syscall)
        log_text("M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n");
    else log_text("M5_C_USER_FRAMES_RECLAIMED\n");
#else
    log_text("M5_C_USER_FRAMES_RECLAIMED\n");
#endif
#else
    log_text("M4_RING3_MAIN_RESTORED\n");
#endif
}

#ifdef HTMLK_M5_USER_FAULT_RECOVER
bool htmlk_m5_user_last_faulted(void) { return user_faulted; }
bool htmlk_m5_user_last_bad_syscall(void) { return user_bad_syscall; }
#ifdef HTMLK_M5_USER_EXIT_STATUS
uint8_t htmlk_m5_user_last_exit_status(void) { return user_exit_code; }
#endif
#ifdef HTMLK_M5_USER_TIMEOUT
bool htmlk_m5_user_last_timed_out(void) { return user_timed_out; }
bool htmlk_m5_timeout_irq_origin_owned(const struct htmlk_m4_d1_irq_frame *f) {
    /* Provenance without trusting saved user RIP/RSP. A forged CPL0 IRQ
     * has no user SS/RSP and MUST NOT reach the five-word frame access. */
    return f && f->cs==user_cs && (f->rflags&0x202U)==0x202U &&
        htmlk_m5_owned_cpu_entry((uintptr_t)f,f->cs,f->ss,f->rflags);
}
bool htmlk_m5_timeout_irq_context_valid(const struct htmlk_m4_d1_irq_frame *f) {
    if (!selected_app_path || user_faulted || user_bad_syscall ||
        user_timed_out || user_exited || frames_registry.live != 6U ||
        !htmlk_m4_saved_main_rsp || !htmlk_m4_saved_cr3 ||
        frames[0] == htmlk_m4_saved_cr3) return false;
    uint64_t current;
    __asm__ volatile("mov %%cr3,%0":"=r"(current));
    const uint64_t rsp0=htmlk_tss_rsp0();
    if ((rsp0 >> 48)!=UINT64_C(0xffff) ||
        (rsp0 & (UINT64_C(1)<<47))==0) return false;
    return htmlk_m5_timeout_frame_valid(f,rsp0,
                                         user_code_length,current,frames[0]);
}
__attribute__((noreturn)) void htmlk_m5_timeout_expire(void) {
    if (user_faulted || user_bad_syscall || user_timed_out || user_exited ||
        frames_registry.live != 6U) reject("M5_E2_BAD_TIMEOUT_STATE\n");
    user_timed_out = true;
    log_text("M5_E2_CPL3_TIMEOUT\n");
    htmlk_m4_user_return();
}
#endif

/* M5-E3-E/F: two fault-only, no-CPU-error-code second-chance proofs
 * for REAL CPL3 #UD/#DE with invalid user RSP. The normal policy stays strict.
 * Do not access arbitrary user memory or recover an ownerless supervisor
 * fault. The caller has already examined CPL3 CS before reading RSP/SS. */
bool htmlk_m5_accept_bad_user_rsp_noerr(unsigned vector,
                                   uintptr_t frame_address,
                                   uint64_t rip, uint64_t cs,
                                   uint64_t flags, uint64_t user_rsp,
                                   uint64_t ss) {
    /* Only the two no-error-code *faults* #DE/#UD use this tiny 40-byte
     * CPU frame. #GP/#PF have error codes; #DB/#BP are traps with different
     * RIP semantics, and must NOT accidentally share this recovery. */
    if (!htmlk_m5_bad_noerr_fault_vector(vector)) return false;
    uint64_t active_cr3;
    __asm__ volatile("mov %%cr3,%0" : "=r"(active_cr3));
    const struct htmlk_m5_bad_noerr_owner ctx = {
        .frame_address=(uint64_t)frame_address,
        .tss_rsp0=htmlk_tss_rsp0(),
        .rip=rip, .cs=cs, .ss=ss, .rflags=flags, .user_rsp=user_rsp,
        .active_cr3=active_cr3, .owned_cr3=frames[0],
        .saved_cr3=htmlk_m4_saved_cr3,
        .saved_main_rsp=(uint64_t)(uintptr_t)htmlk_m4_saved_main_rsp,
        .code_bytes=user_code_length,
        .live_frames=frames_registry.live,
        .has_active_app=selected_app_path != 0,
        .already_terminated=user_faulted || user_bad_syscall || user_exited
#ifdef HTMLK_M5_USER_TIMEOUT
            || user_timed_out
#endif
        ,
#ifdef HTMLK_M5_USER_TIMEOUT
        .expected_if=true,
#else
        .expected_if=false,
#endif
    };
    if (!htmlk_m5_bad_noerr_stack_owned(&ctx)) return false;
    user_faulted=true;
    log_text(vector == 0U ? "M5_E3_USER_DE_BAD_RSP_RETIRED\n" :
                            "M5_E3_USER_UD_BAD_RSP_RETIRED\n");
    return true;
}

/* M5-E3-I: real trap-class #DB/#BP with damaged saved user RSP.
 * The same five-qword CPU frame is on trusted TSS.RSP0 as #UD/#DE,
 * but the saved RIP points *after* ICEBP/INT3 (possibly code-end).
 * Validate the exact trap vector, frame, CR3 and live owner separately. */
bool htmlk_m5_accept_bad_user_rsp_trap(unsigned vector,
                                   uintptr_t frame_address,
                                   uint64_t rip, uint64_t cs,
                                   uint64_t flags, uint64_t user_rsp,
                                   uint64_t ss) {
    if (vector != 1U && vector != 3U) return false;
    uint64_t current_cr3;
    __asm__ volatile("mov %%cr3,%0" : "=r"(current_cr3));
    const struct htmlk_m5_bad_noerr_owner proof = {
        .frame_address=(uint64_t)frame_address,
        .tss_rsp0=htmlk_tss_rsp0(),
        .rip=rip,.cs=cs,.ss=ss,.rflags=flags,.user_rsp=user_rsp,
        .active_cr3=current_cr3,.owned_cr3=frames[0],
        .saved_cr3=htmlk_m4_saved_cr3,
        .saved_main_rsp=(uint64_t)(uintptr_t)htmlk_m4_saved_main_rsp,
        .code_bytes=user_code_length,
        .live_frames=frames_registry.live,
        .has_active_app=selected_app_path != 0,
        .already_terminated=user_faulted || user_bad_syscall || user_exited
#ifdef HTMLK_M5_USER_TIMEOUT
            || user_timed_out
#endif
        ,
#ifdef HTMLK_M5_USER_TIMEOUT
        .expected_if=true,
#else
        .expected_if=false,
#endif
    };
    if (!htmlk_m5_bad_trap_stack_owned(vector,&proof)) return false;
    user_faulted=true;
    log_text(vector == 1U ? "M5_E3_USER_DB_BAD_RSP_RETIRED\n" :
                            "M5_E3_USER_BP_BAD_RSP_RETIRED\n");
    return true;
}

/* M5-E3-G: strictly vector 13 CPU-error-code frame on TSS.RSP0.
 * Do not reuse the #UD/#DE 40-byte layout: #GP has an 8-byte error word,
 * though the GCC interrupt_frame * points at the following RIP. */
bool htmlk_m5_accept_bad_user_rsp_gp(uintptr_t cpu_frame,
                                  uintptr_t cpu_error_word,
                                  uint64_t rip, uint64_t cs, uint64_t flags,
                                  uint64_t user_rsp, uint64_t ss,
                                  uint64_t error) {
    uint64_t active_cr3;
    __asm__ volatile("mov %%cr3,%0" : "=r"(active_cr3));
    const struct htmlk_m5_bad_gp_owner proof = {
        .frame = {
            .frame_address=(uint64_t)cpu_frame,
            .tss_rsp0=htmlk_tss_rsp0(),
            .rip=rip,.cs=cs,.ss=ss,.rflags=flags,.user_rsp=user_rsp,
            .active_cr3=active_cr3,.owned_cr3=frames[0],
            .saved_cr3=htmlk_m4_saved_cr3,
            .saved_main_rsp=(uint64_t)(uintptr_t)htmlk_m4_saved_main_rsp,
            .code_bytes=user_code_length,
            .live_frames=frames_registry.live,
            .has_active_app=selected_app_path != 0,
            .already_terminated=user_faulted || user_bad_syscall || user_exited
#ifdef HTMLK_M5_USER_TIMEOUT
                || user_timed_out
#endif
            ,
#ifdef HTMLK_M5_USER_TIMEOUT
            .expected_if=true,
#else
            .expected_if=false,
#endif
        },
        .error_word_address=(uint64_t)cpu_error_word,
        .error_code=error,
    };
    if (!htmlk_m5_bad_gp_stack_owned(&proof)) return false;
    user_faulted=true;
    log_text("M5_E3_USER_GP_BAD_RSP_RETIRED\n");
    return true;
}

/* M5-E3-H: unlike #GP at TSS.RSP0, #PF always changes to IST2.
 * Prove exact CPU frame and error word relative to trusted TSS IST2 top;
 * restore only the active owned CPL3 app after strict PF guard rejects
 * its poisoned *user* RSP. Never dereference that RSP or CR2. */
bool htmlk_m5_accept_bad_user_rsp_pf(uintptr_t cpu_frame,
                                  uintptr_t cpu_error_word,
                                  uint64_t rip, uint64_t cs, uint64_t flags,
                                  uint64_t user_rsp, uint64_t ss,
                                  uint64_t error, uint64_t cr2) {
    uint64_t current_cr3;
    __asm__ volatile("mov %%cr3,%0" : "=r"(current_cr3));
    const uint64_t ist2_top = htmlk_tss_pf_ist2_top();
    const struct htmlk_m5_bad_pf_owner proof = {
        .frame = {
            .frame_address=(uint64_t)cpu_frame,
            .tss_rsp0=ist2_top,
            .rip=rip,.cs=cs,.ss=ss,.rflags=flags,.user_rsp=user_rsp,
            .active_cr3=current_cr3,.owned_cr3=frames[0],
            .saved_cr3=htmlk_m4_saved_cr3,
            .saved_main_rsp=(uint64_t)(uintptr_t)htmlk_m4_saved_main_rsp,
            .code_bytes=user_code_length,
            .live_frames=frames_registry.live,
            .has_active_app=selected_app_path != 0,
            .already_terminated=user_faulted || user_bad_syscall || user_exited
#ifdef HTMLK_M5_USER_TIMEOUT
                || user_timed_out
#endif
            ,
#ifdef HTMLK_M5_USER_TIMEOUT
            .expected_if=true,
#else
            .expected_if=false,
#endif
        },
        .ist2_top=ist2_top,
        .error_word_address=(uint64_t)cpu_error_word,
        .error_code=error,
        .cr2=cr2,
    };
    if (!htmlk_m5_bad_pf_stack_owned(&proof)) return false;
    switch (error) {
        case 4U: log_text("M5_E3_USER_PF4_GUARD_BAD_RSP_RETIRED\n"); break;
        case 6U: log_text("M5_E3_USER_PF6_GUARD_BAD_RSP_RETIRED\n"); break;
        case 5U: log_text("M5_E3_USER_PF5_BAD_RSP_RETIRED\n"); break;
        case 7U: log_text("M5_E3_USER_PF7_BAD_RSP_RETIRED\n"); break;
        default: return false; /* policy above admits exactly these codes */
    }
    user_faulted=true;
    return true;
}

bool htmlk_m5_accept_user_fault(unsigned vector, uint64_t rip,
                                uint64_t cs, uint64_t flags,
                                uint64_t rsp, uint64_t ss,
                                uint64_t error, uint64_t cr2) {
    /* Accept only a real CPL3 fault from an active known process, never
     * a kernel fault, reused frame, forged selector or wrong CR3.
     * For #PF only the CPU error's U/S bit is trusted; user-controlled
     * addresses are not dereferenced by this handler. */
    if (!selected_app_path || user_faulted || user_bad_syscall || user_exited ||
#ifdef HTMLK_M5_USER_TIMEOUT
        user_timed_out ||
#endif
        frames_registry.live != 6U || !htmlk_m4_saved_main_rsp ||
        !htmlk_m4_saved_cr3 || frames[0] == htmlk_m4_saved_cr3)
        return false;
    uint64_t current_cr3;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(current_cr3));
    if (!htmlk_m5_user_fault_frame_valid(vector,rip,cs,flags,rsp,ss,
                                          error,current_cr3,frames[0],
                                          user_code_length))
        return false;
    (void)cr2; /* CR2 is diagnostic only; no generic fixup on arbitrary faults. */
    user_faulted = true;
    switch (vector) {
        case 0U: log_text("M5_E_USER_DE\n"); break;
        case 1U: log_text("M5_E_USER_DB\n"); break;
        case 3U: log_text("M5_E_USER_BP\n"); break;
        case 6U: log_text("M5_E_USER_UD\n"); break;
        case 13U: log_text("M5_E_USER_GP_0\n"); break;
        case 14U:
            if (error == 5U) log_text("M5_E_USER_PF_5\n");
            else if (error == 7U) log_text("M5_E_USER_PF_7\n");
            else log_text("M5_E_USER_PF_OTHER\n");
            break;
        default: return false;
    }
    return true;
}
#endif

#ifdef HTMLK_M5_INTERACTIVE_RUN
void htmlk_m5_user_run(const char *path,
                       const struct limine_memmap_response *map,
                       const struct limine_hhdm_response *hhdm) {
    selected_app_path = path;
    htmlk_m4_user_probe(map, hhdm);
    selected_app_path = 0;
}
#endif
