/* Minimal Limine base-revision-6 handoff into code generated from HTML. */
#include <stdint.h>
#if defined(HTMLK_M5_ROMFS_PROBE) || defined(HTMLK_M5_SERIAL_CONSOLE)
#include "romfs.h"
#endif
#ifdef HTMLK_M5_ROMFS_PROBE
extern void htmlk_m5_romfs_probe(void);
#endif
#ifdef HTMLK_M5_SERIAL_CONSOLE
extern void htmlk_m5_serial_console(void);
#endif
#include "limine.h"
#ifdef HTMLK_M4_TASK_PROBE
#include "task_runtime.h"
#endif
#ifdef HTMLK_M4_X2APIC_PREEMPT
#include "preempt_x2apic.h"
#endif
#ifdef HTMLK_M4_USER_PROBE
#include "user_probe.h"
#endif
#ifdef HTMLK_M4_USER_ISOLATION
#include "user_isolation.h"
#endif
#ifdef HTMLK_M4_TIMER_PROBE
#include "timer_irq.h"
#endif
#ifdef HTMLK_M3_IST_STACK
#include "tss_ist.h"
#endif
#ifdef HTMLK_M3_EXCEPTION_IDT
#include "exception_idt.h"
#endif
#ifdef HTMLK_FB_CONSOLE
#include "console_fb.h"
#endif
#ifdef HTMLK_M3_MEMORY_PROBE
#include "memory_probe.h"
#endif
#ifdef HTMLK_M3_PAGING_PROBE
#include "paging_probe.h"
#endif

__attribute__((used, section(".limine_requests_start")))
static volatile uint64_t start_marker[] = LIMINE_REQUESTS_START_MARKER;

__attribute__((used, section(".limine_requests")))
static volatile uint64_t base_revision[] = LIMINE_BASE_REVISION(6);

__attribute__((used, section(".limine_requests_end")))
static volatile uint64_t end_marker[] = LIMINE_REQUESTS_END_MARKER;

#if defined(HTMLK_M3_MEMORY_PROBE) || defined(HTMLK_M3_PAGING_PROBE) || \
    defined(HTMLK_M4_USER_PROBE) || defined(HTMLK_M4_USER_ISOLATION)
/* Opt-in requests reside within the pinned Limine request marker section.
 * Production/default boot tests remain untouched unless M3 memory/paging is enabled.
 */
__attribute__((used, section(".limine_requests")))
static volatile struct limine_memmap_request m3_memmap_request = {
    .id = LIMINE_MEMMAP_REQUEST_ID, .revision = 0, .response = 0
};
__attribute__((used, section(".limine_requests")))
static volatile struct limine_hhdm_request m3_hhdm_request = {
    .id = LIMINE_HHDM_REQUEST_ID, .revision = 0, .response = 0
};
#endif

#ifdef HTMLK_FB_CONSOLE
__attribute__((used, section(".limine_requests")))
static volatile struct limine_framebuffer_request fb_request = {
    .id = LIMINE_FRAMEBUFFER_REQUEST_ID, .revision = 0, .response = 0
};

static void configure_framebuffer(void) {
    const struct limine_framebuffer_response *response = fb_request.response;
    if (response == 0 || response->framebuffer_count == 0 ||
        response->framebuffers == 0 || response->framebuffers[0] == 0) {
        return; /* Serial/debugcon remains the fallback. */
    }
    const struct limine_framebuffer *frame = response->framebuffers[0];
    const struct htmlk_fb_mode mode = {
        .address = (volatile uint8_t *)frame->address,
        .width = frame->width,
        .height = frame->height,
        .pitch = frame->pitch,
        .bpp = frame->bpp,
        .memory_model = frame->memory_model,
        .red_size = frame->red_mask_size,
        .red_shift = frame->red_mask_shift,
        .green_size = frame->green_mask_size,
        .green_shift = frame->green_mask_shift,
        .blue_size = frame->blue_mask_size,
        .blue_shift = frame->blue_mask_shift
    };
    (void)htmlk_fb_init(&mode);
}
#endif

extern void kernel_main(void);
__attribute__((noreturn))
void kmain(void) {
    if (!LIMINE_BASE_REVISION_SUPPORTED(base_revision)) {
        /* Unsupported boot protocol: never silently enter the kernel. */
#ifdef HTMLK_QEMU_TEST_EXIT
        __asm__ volatile ("outb %0, %1" : :
                          "a"((unsigned char)0x11), "Nd"((unsigned short)0xf4));
#endif
        for (;;) __asm__ volatile ("cli; hlt");
    }
#ifdef HTMLK_M3_IST_STACK
    htmlk_tss_ist_install(); /* load our own valid code/data GDT + 64-bit TSS */
#endif
#ifdef HTMLK_M3_EXCEPTION_IDT
    htmlk_idt_install(); /* install fail-stop CPU exceptions before probes */
#if defined(HTMLK_M3_FAULT_UD) || defined(HTMLK_M3_FAULT_PF) || \
    defined(HTMLK_M3_FAULT_DE) || defined(HTMLK_M3_FAULT_GP)
    htmlk_idt_inject_test_fault(); /* real CPU exception, no return */
#endif
#ifdef HTMLK_M3_DOUBLE_FAULT_TEST
    htmlk_tss_inject_double_fault(); /* corrupted RSP forces true #DF on IST1 */
#endif
#endif
#ifdef HTMLK_M3_MEMORY_PROBE
    htmlk_memory_probe(m3_memmap_request.response, m3_hhdm_request.response);
#endif
#ifdef HTMLK_M3_PAGING_PROBE
    htmlk_paging_probe(m3_memmap_request.response, m3_hhdm_request.response);
#endif
#ifdef HTMLK_FB_CONSOLE
    configure_framebuffer();
#endif
#ifdef HTMLK_M4_TIMER_PROBE
    htmlk_m4_timer_init(); /* Real PIT/PIC IRQ0, installed IDT vector 32. */
#endif
#ifdef HTMLK_M4_TASK_PROBE
    htmlk_m4_task_probe(); /* Opt-in, ring-0 only cooperative task proof. */
#endif
#ifdef HTMLK_M4_TIMER_PROBE
    htmlk_m4_timer_finish(); /* Mask IRQ0 before entering source-derived HTML. */
#endif
#ifdef HTMLK_M4_X2APIC_PREEMPT
    htmlk_m4_preempt_probe(); /* Real timer preempts non-yielding ring-0 tasks. */
#endif
#ifdef HTMLK_M4_USER_PROBE
    htmlk_m4_user_probe(m3_memmap_request.response, m3_hhdm_request.response);
#endif
#ifdef HTMLK_M4_USER_ISOLATION
    htmlk_m4_user_isolation_probe(m3_memmap_request.response,
                                  m3_hhdm_request.response);
#endif
#ifdef HTMLK_M5_ROMFS_PROBE
    htmlk_m5_romfs_probe(); /* Real immutable ELF .rodata bytes, not UI. */
#endif
#ifdef HTMLK_M5_SERIAL_CONSOLE
    htmlk_m5_serial_console(); /* Real 16550 UART RX, bounded ROMFS commands. */
#endif
    kernel_main(); /* Generated from examples/kernel.html. */
    for (;;) __asm__ volatile ("cli; hlt");
}
