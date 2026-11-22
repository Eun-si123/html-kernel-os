/* Minimal Limine base-revision-6 handoff into code generated from HTML. */
#include <stdint.h>
#include "limine.h"

__attribute__((used, section(".limine_requests_start")))
static volatile uint64_t start_marker[] = LIMINE_REQUESTS_START_MARKER;

__attribute__((used, section(".limine_requests")))
static volatile uint64_t base_revision[] = LIMINE_BASE_REVISION(6);

__attribute__((used, section(".limine_requests_end")))
static volatile uint64_t end_marker[] = LIMINE_REQUESTS_END_MARKER;

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
    kernel_main(); /* Generated from examples/kernel.html. */
    for (;;) __asm__ volatile ("cli; hlt");
}
