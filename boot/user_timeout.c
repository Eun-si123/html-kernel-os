/* M5-E2: reuse the same real CPU IRQ frame/assembly as M4-D, but enforce
 * one finite user program time slice and resume its existing kernel shell.
 * QEMU-only, 1 vCPU, no nested IRQ, no FPU/SIMD/FS/GS state contract. */
#include "user_timeout.h"
#include "user_probe.h"
#include <stdint.h>
#include <stdbool.h>

enum { TICKS_ALLOWED = 4U };
#define APIC_BASE 0x1bU
#define APIC_EOI 0x80bU
#define APIC_SVR 0x80fU
#define APIC_TPR 0x808U
#define APIC_LVT 0x832U
#define APIC_INIT 0x838U
#define APIC_DIV 0x83eU

/* Defined only to satisfy the dormant main-stack return branch in M4-D's
 * shared IRQ assembly. This mode NEVER takes that branch: timeout returns
 * via the saved M5 user-run main stack and original CR3. */
uint64_t *htmlk_m4_d1_main_rsp;
static unsigned ticks;
static bool timer_active;

static void out(uint16_t port,uint8_t value) {
    __asm__ volatile("outb %0,%1" :: "a"(value),"Nd"(port):"memory");
}
static void log_text(const char *s) {
    while (*s) out(0xe9U,(uint8_t)*s++);
}
__attribute__((noreturn)) static void fail(const char *reason) {
    __asm__ volatile("cli" ::: "memory");
    log_text(reason);
#ifdef HTMLK_QEMU_TEST_EXIT
    out(0xf4U,0x1cU); /* QEMU exit 57 */
#endif
    for (;;) __asm__ volatile("cli;hlt");
}
static uint64_t read_msr(uint32_t address) {
    uint32_t low,high;
    __asm__ volatile("rdmsr":"=a"(low),"=d"(high):"c"(address));
    return ((uint64_t)high<<32) | low;
}
static void write_msr(uint32_t address,uint64_t value) {
    __asm__ volatile("wrmsr"::"c"(address),"a"((uint32_t)value),
                     "d"((uint32_t)(value>>32)):"memory");
}
void htmlk_m5_timeout_start(void) {
    __asm__ volatile("cli" ::: "memory");
    if (timer_active) fail("M5_E2_TIMER_DOUBLE_START\n");
    uint32_t a,b,c,d;
    __asm__ volatile("cpuid":"=a"(a),"=b"(b),"=c"(c),"=d"(d)
                     :"a"(1U),"c"(0U));
    (void)a;(void)b;
    if (!(d&(1U<<9)) || !(c&(1U<<21)))
        fail("M5_E2_X2APIC_REQUIRED\n");
    const uint64_t base=read_msr(APIC_BASE);
    if (!(base&(1ULL<<11))) fail("M5_E2_APIC_DISABLED\n");
    write_msr(APIC_BASE,base|(1ULL<<10));
    if ((read_msr(APIC_BASE)&(3ULL<<10))!=(3ULL<<10))
        fail("M5_E2_X2APIC_NOT_ACTIVE\n");
    out(0x21U,0xffU);out(0xa1U,0xffU); /* mask legacy PIC */
    write_msr(APIC_TPR,0U);
    write_msr(APIC_SVR,0x1ffU);
    write_msr(APIC_DIV,3U);
#ifdef HTMLK_M5_USER_TIMEOUT_MASK
    write_msr(APIC_LVT,0x30040U);
#else
    write_msr(APIC_LVT,0x20040U);
#endif
    ticks=0U;
    timer_active=true;
    write_msr(APIC_INIT,1000000U); /* deliberately uncalibrated QEMU budget */
    log_text("M5_E2_X2APIC_TIMER_READY\n");
}
void htmlk_m5_timeout_stop(void) {
    __asm__ volatile("cli" ::: "memory");
    if (!timer_active) fail("M5_E2_TIMER_NOT_ACTIVE\n");
    write_msr(APIC_LVT,0x30040U);
    write_msr(APIC_INIT,0U);
    timer_active=false;
}
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_on_irq(
    struct htmlk_m4_d1_irq_frame *frame) {
    if (!timer_active) fail("M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT\n");
    if (!htmlk_m5_timeout_irq_context_valid(frame)) {
        /* A genuinely owned Ring3 task may smash its own RIP/RSP then
         * spin forever. This is *user* corruption, not kernel corruption.
         * Retire the task only after an independent exact TSS/RSP0,
         * privilege, original CR3/stack and owner-registry proof; never
         * dereference the faulty user RSP or attempt to IRET through it.
         * Unexpected CPL0/wrong-CR3/stale/unowned interrupts stay fatal. */
        if (htmlk_m5_timeout_irq_origin_owned(frame)) {
            log_text("M5_E3_USER_IRQ_FRAME_INVALID\n");
            write_msr(APIC_EOI,0U); /* actual IRQ accepted before abort */
            htmlk_m5_timeout_expire();
        }
        fail("M5_E2_UNTRUSTED_RING3_IRQ_CONTEXT\n");
    }
    if (++ticks > TICKS_ALLOWED)
        fail("M5_E2_TICK_BUDGET_OVERFLOW\n");
    if (ticks == 1U) log_text("M5_E2_REAL_USER_IRQ_1\n");
    if (ticks >= TICKS_ALLOWED) {
        log_text("M5_E2_REAL_USER_IRQ_LIMIT\n");
        write_msr(APIC_EOI,0U);
        /* Leave APIC configured; the caller immediately restores the
         * kernel stack/CR3, disables IRQ and masks the timer on return. */
        htmlk_m5_timeout_expire(); /* does not return to interrupted Ring3 */
    }
    write_msr(APIC_EOI,0U);
    return frame; /* shared M4-D ISR restores all GPR and IRETQ */
}
