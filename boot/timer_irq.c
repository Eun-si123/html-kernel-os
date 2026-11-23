#include "timer_irq.h"
#include <stdint.h>
/* Real legacy 8254 PIT -> 8259A PIC IRQ0 at remapped vector 0x20.
 * Opt-in QEMU proof only. Interrupt handlers never switch task stacks. */
static volatile uint64_t ticks;
static void out(uint16_t port, uint8_t byte) {
    __asm__ volatile ("outb %0, %1" : : "a"(byte), "Nd"(port) : "memory");
}
static uint8_t in(uint16_t port) {
    uint8_t value;
    __asm__ volatile ("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}
static void debug_text(const char *msg) {
    while (*msg) out(0xe9, (uint8_t)*msg++);
}
__attribute__((noreturn))
static void failed(const char *msg) {
    __asm__ volatile ("cli" ::: "memory");
    debug_text(msg);
#ifdef HTMLK_QEMU_TEST_EXIT
    out(0xf4, 0x18); /* Negative QEMU exit 49. */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
uint16_t htmlk_m4_pit_divisor(unsigned hz) {
    if (hz < 19U || hz > 1193182U) return 0;
    uint32_t div = 1193182U / hz;
    if (div == 0 || div > 65535U) return 0;
    return (uint16_t)div;
}
void htmlk_m4_irq0_handler(void) {
    ++ticks;
    out(0x20, 0x20); /* PIC1 specific end-of-interrupt. */
}
struct m4_interrupt_frame {
    uint64_t rip, cs, flags, rsp, ss;
};
__attribute__((interrupt))
void htmlk_m4_irq0_entry(struct m4_interrupt_frame *frame) {
    (void)frame;
    htmlk_m4_irq0_handler();
}
void htmlk_m4_timer_init(void) {
    __asm__ volatile ("cli" ::: "memory");
    /* Legacy PIC IRQ routing is not guaranteed when the virtual local APIC
     * exists. Fail visibly rather than silently hanging on a missing IRQ. */
    uint32_t eax, ebx, ecx, edx;
    __asm__ volatile ("cpuid" : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                      : "a"(1U), "c"(0U));
    (void)eax; (void)ebx; (void)ecx;
    if ((edx & (1U << 9)) != 0)
        failed("M4_TIMER_APIC_UNSUPPORTED\n");
    ticks = 0;
    /* Remap PIC vector 0x08 -> 0x20; mask all IRQs except IRQ0.
     * Read old masks for audit (not restored: this is an opt-in test ISO). */
    (void)in(0x21);
    (void)in(0xA1);
    out(0x20, 0x11);
    out(0xA0, 0x11);
    out(0x21, 0x20);
    out(0xA1, 0x28);
    out(0x21, 0x04);
    out(0xA1, 0x02);
    out(0x21, 0x01);
    out(0xA1, 0x01);
    out(0xA1, 0xff);
#ifdef HTMLK_M4_TIMER_MASK_TEST
    out(0x21, 0xff); /* Deliberately forbid IRQ0 for bounded timeout oracle. */
#else
    out(0x21, 0xfe);
#endif
    const uint16_t divisor = htmlk_m4_pit_divisor(100);
    if (!divisor) failed("M4_TIMER_DIVISOR_INVALID\n");
    out(0x43, 0x34); /* PIT channel 0, low/high, periodic rate generator. */
    out(0x40, (uint8_t)divisor);
    out(0x40, (uint8_t)(divisor >> 8));
    debug_text("M4_TIMER_READY\n");
}
void htmlk_m4_timer_wait(void) {
    const uint64_t before = ticks;

    /* STI interrupt shadow prevents a lost wakeup before HLT. On return,
     * IRQ0 must have been delivered and acknowledged; no fake timer count. */
    __asm__ volatile ("sti; hlt; cli" ::: "memory");
    if (ticks <= before) failed("M4_TIMER_NO_IRQ0\n");
}
void htmlk_m4_timer_finish(void) {
    __asm__ volatile ("cli" ::: "memory");
    out(0x21, 0xff);
    out(0xA1, 0xff);
    if (ticks < 6) failed("M4_TIMER_TOO_FEW_IRQS\n");
    debug_text("M4_TIMER_IRQ_PASS\n");
}
