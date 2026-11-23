#include "user_preempt.h"
#include "user_pages.h"
#include "page_pool.h"
#include "frame_owner.h"
#include "tss_ist.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

/* Opt-in fixed-image 1-vCPU CPL3 scheduler, NOT a general process loader. */
enum { KSTACK=2048, LIMIT=256, STEPS=3 };
#define CANARY UINT64_C(0xf7e1c034569abdef)
#define APIC_BASE 0x1bU
#define APIC_EOI 0x80bU
#define APIC_SVR 0x80fU
#define APIC_TPR 0x808U
#define APIC_LVT 0x832U
#define APIC_DIV 0x83eU
#define APIC_INIT 0x838U
uint64_t *htmlk_m4_d1_main_rsp;
static uint64_t kstack[2][KSTACK] __attribute__((aligned(16)));
static struct htmlk_m4_d1_irq_frame *saved[2];
static struct htmlk_frame_registry owners;
static uint64_t phys[2][6], hhdm, old_cr3, old_rsp0;
static uint64_t image_len[2], loop_off[2], progress[2], samples[2];
static uint64_t ticks, switches;
static unsigned active;
#ifdef HTMLK_M4_D2_FAULT
static bool retired_a;
#endif
static void out(uint16_t p,uint8_t b) {
    __asm__ volatile("outb %0,%1"::"a"(b),"Nd"(p):"memory");
}
static void log_text(const char *s) {
    while (*s) out(0xe9U,(uint8_t)*s++);
}
__attribute__((noreturn)) static void fail(const char *s) {
    __asm__ volatile("cli":::"memory");
    log_text(s);
#ifdef HTMLK_QEMU_TEST_EXIT
    out(0xf4U,0x1cU); /* (0x1c<<1)|1 => 57 */
#endif
    for (;;) __asm__ volatile("cli; hlt");
}
static uint64_t cr3_now(void) {
    uint64_t r;
    __asm__ volatile("mov %%cr3,%0":"=r"(r));
    return r;
}
static uint64_t rdmsr(uint32_t n) {
    uint32_t lo,hi;
    __asm__ volatile("rdmsr":"=a"(lo),"=d"(hi):"c"(n));
    return ((uint64_t)hi<<32)|lo;
}
static void wrmsr(uint32_t n,uint64_t v) {
    __asm__ volatile("wrmsr"::"c"(n),"a"((uint32_t)v),
                     "d"((uint32_t)(v>>32)):"memory");
}
static void timer_start(void) {
    uint32_t a,b,c,d;
    __asm__ volatile("cpuid":"=a"(a),"=b"(b),"=c"(c),"=d"(d)
                     :"a"(1U),"c"(0U));
    (void)a;(void)b;
    if (!(d&(1U<<9)) || !(c&(1U<<21))) fail("M4_D1_NO_X2APIC\n");
    const uint64_t base=rdmsr(APIC_BASE);
    if (!(base&(1ULL<<11))) fail("M4_D1_APIC_DISABLED\n");
    wrmsr(APIC_BASE,base|(1ULL<<10));
    if ((rdmsr(APIC_BASE)&(3ULL<<10))!=(3ULL<<10))
        fail("M4_D1_APIC_NOT_ACTIVE\n");
    out(0x21U,0xffU);out(0xa1U,0xffU); /* legacy PIC masked */
    wrmsr(APIC_TPR,0);wrmsr(APIC_SVR,0x1ffU);
    wrmsr(APIC_DIV,3U);
#ifdef HTMLK_M4_D1_TIMER_MASK
    wrmsr(APIC_LVT,0x30040U);
#else
    wrmsr(APIC_LVT,0x20040U);
#endif
    wrmsr(APIC_INIT,1000000U);
    log_text("M4_D1_TIMER_READY\n");
}
static void timer_stop(void) {
    wrmsr(APIC_LVT,0x30040U);
    wrmsr(APIC_INIT,0U);
}
static uint64_t top(unsigned i) {
    return (uint64_t)(uintptr_t)&kstack[i][KSTACK];
}
static uint64_t slot(unsigned i,unsigned offset) {
    const volatile uint64_t *p=(const volatile uint64_t *)(uintptr_t)
        (hhdm+phys[i][5]+HTMLK_PAGE_SIZE-offset);
    return *p;
}
#ifdef HTMLK_M4_D2_FAULT
static void set_slot(unsigned i,unsigned offset,uint64_t value) {
    volatile uint64_t *p=(volatile uint64_t *)(uintptr_t)
        (hhdm+phys[i][5]+HTMLK_PAGE_SIZE-offset);
    *p=value;
}
#endif
static bool valid(unsigned i,const struct htmlk_m4_d1_irq_frame *f) {
    if (i>=2 || kstack[i][0]!=CANARY) return false;
    const uint64_t bx=i==0?UINT64_C(0x123456789abcdef0):
        UINT64_C(0xfedcba9876543210);
    const uint64_t r12=i==0?UINT64_C(0x76543210fedcba98):
        UINT64_C(0x89abcdef01234567);
    return htmlk_m4_d1_frame_guard(f,
        (uintptr_t)&kstack[i][64],(uintptr_t)top(i),
        image_len[i],loop_off[i],bx,r12);
}
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_on_irq(
    struct htmlk_m4_d1_irq_frame *f) {
    const unsigned i=active;
    if (i>=2 || cr3_now()!=phys[i][0] ||
        htmlk_tss_rsp0()!=top(i) || !valid(i,f))
        fail("M4_D1_IRQ_CONTEXT_INVALID\n");
    saved[i]=f;
    if (++ticks>LIMIT) fail("M4_D1_TICK_TIMEOUT\n");
    const uint64_t sentinel=slot(i,24U), counter=slot(i,32U);
#ifdef HTMLK_M4_D2_FAULT
    const uint64_t goal=i==0U?2U:5U;
#else
    const uint64_t goal=STEPS;
#endif
    if (sentinel==(i==0?0xa11aU:0xb22bU) &&
        counter>samples[i] && progress[i]<goal) {
        samples[i]=counter;
        log_text("M4_D1_USER_");
        out(0xe9U,i==0?'A':'B');out(0xe9U,'_');
        out(0xe9U,(uint8_t)('0'+progress[i]));out(0xe9U,'\n');
        ++progress[i];
    }
#ifdef HTMLK_M4_D2_FAULT
    if (!retired_a && progress[0]>=2 && progress[1]>=2)
        set_slot(0U,56U,1U); /* A must fault on its next ring3 time slice */
#ifdef HTMLK_M4_D2_B_FAULT
    if (retired_a && progress[1]>=3)
        set_slot(1U,56U,1U); /* unexpected B fault must fail-stop */
#endif
    const bool completed=retired_a && progress[1]>=5;
#else
    const bool completed=progress[0]==STEPS && progress[1]==STEPS;
#endif
    if (completed) {
        if (switches<5 || slot(1,24U)!=0xb22bU ||
            phys[0][0]==phys[1][0] || phys[0][5]==phys[1][5])
            fail("M4_D1_PROGRESS_OR_ISOLATION_INVALID\n");
#ifndef HTMLK_M4_D2_FAULT
        if (slot(0,24U)!=0xa11aU)
            fail("M4_D1_A_SENTINEL_CORRUPT\n");
#endif
        timer_stop();wrmsr(APIC_EOI,0U);
#ifdef HTMLK_M4_D2_FAULT
        if (!retired_a || owners.live!=6)
            fail("M4_D2_OFFENDER_NOT_RECLAIMED\n");
        log_text("M4_D2_CPL3_FAULT_SURVIVOR_PASS\n");
#else
        log_text("M4_D1_CPL3_PREEMPT_PASS\n");
#endif
        htmlk_tss_set_rsp0(old_rsp0);
        __asm__ volatile("mov %0,%%cr3"::"r"(old_cr3):"memory");
        return NULL; /* assembly restores main kernel stack */
    }
#ifdef HTMLK_M4_D2_FAULT
    const unsigned next=retired_a?1U:i^1U;
#else
    const unsigned next=i^1U;
#endif
    if (!valid(next,saved[next])) fail("M4_D1_NEXT_FRAME_INVALID\n");
    ++switches;
    active=next;
    htmlk_tss_set_rsp0(top(next));
    __asm__ volatile("mov %0,%%cr3"::"r"(phys[next][0]):"memory");
    wrmsr(APIC_EOI,0U);
    return saved[next];
}
static void task_init(unsigned i,const unsigned char *begin,
                      const unsigned char *end,const unsigned char *loop,
                      volatile uint64_t *original) {
    if (end<=begin || (uint64_t)(end-begin)>HTMLK_PAGE_SIZE ||
        loop<begin || loop>=end)
        fail("M4_D1_BAD_USER_IMAGE\n");
    image_len[i]=(uint64_t)(end-begin);
    loop_off[i]=(uint64_t)(loop-begin);
    volatile uint64_t *root=(volatile uint64_t *)(uintptr_t)(hhdm+phys[i][0]);
    volatile uint64_t *pdpt=(volatile uint64_t *)(uintptr_t)(hhdm+phys[i][1]);
    volatile uint64_t *pd=(volatile uint64_t *)(uintptr_t)(hhdm+phys[i][2]);
    volatile uint64_t *pt=(volatile uint64_t *)(uintptr_t)(hhdm+phys[i][3]);
    volatile uint8_t *code=(volatile uint8_t *)(uintptr_t)(hhdm+phys[i][4]);
    volatile uint8_t *stack=(volatile uint8_t *)(uintptr_t)(hhdm+phys[i][5]);
    for (unsigned j=0;j<512;j++)
        root[j]=original[j]&~HTMLK_M4_USER_BIT;
    for (unsigned j=0;j<HTMLK_PAGE_SIZE;j++) {
        code[j]=j<image_len[i]?begin[j]:0U;
        stack[j]=0U;
    }
    if (!htmlk_m4_user_wire(root,pdpt,pd,pt,phys[i]) ||
        (root[HTMLK_M4_USER_SLOT]&7U)!=7U ||
        (pt[0]&7U)!=5U || (pt[1]&7U)!=7U)
        fail("M4_D1_UNSAFE_PAGES\n");
    for (unsigned j=0;j<KSTACK;j++) kstack[i][j]=0;
    kstack[i][0]=CANARY;
    saved[i]=(struct htmlk_m4_d1_irq_frame *)(uintptr_t)
        (top(i)-sizeof(*saved[i]));
    saved[i]->rip=HTMLK_M4_USER_BASE;
    saved[i]->cs=0x2bU;
    saved[i]->rflags=0x202U;
    saved[i]->rsp=HTMLK_M4_USER_STACK-16U;
    saved[i]->ss=0x33U;
    if (!valid(i,saved[i])) fail("M4_D1_INVALID_INITIAL_FRAME\n");
}
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *map,
                                  const struct limine_hhdm_response *addr) {
    __asm__ volatile("cli":::"memory");
    if (!map || !addr || !map->entries || map->entry_count==0 ||
        map->entry_count>HTMLK_MAX_MEMORY_REGIONS)
        fail("M4_D1_INVALID_MEMMAP\n");
    uint64_t cr4;
    __asm__ volatile("mov %%cr4,%0":"=r"(cr4));
    if (cr4&((UINT64_C(1)<<12)|(UINT64_C(1)<<17)))
        fail("M4_D1_LA57_PCID_UNSUPPORTED\n");
    struct htmlk_phys_range areas[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t j=0;j<map->entry_count;j++) {
        if (!map->entries[j]) fail("M4_D1_NULL_REGION\n");
        areas[j].base=map->entries[j]->base;
        areas[j].length=map->entries[j]->length;
        areas[j].type=map->entries[j]->type;
    }
    struct htmlk_page_pool pool={0};
    if (!htmlk_page_pool_init(areas,map->entry_count,&pool) ||
        !htmlk_frames_init(&owners,&pool))
        fail("M4_D1_POOL_INVALID\n");
    old_cr3=cr3_now();old_rsp0=htmlk_tss_rsp0();hhdm=addr->offset;
    if (!old_cr3 || (old_cr3&~HTMLK_M4_USER_PHYS_MASK) ||
        !old_rsp0 || !hhdm || (hhdm&(HTMLK_PAGE_SIZE-1U)) ||
        hhdm>UINT64_MAX-old_cr3-HTMLK_PAGE_SIZE)
        fail("M4_D1_BAD_CR3_HHDM\n");
    for (unsigned i=0;i<2;i++) for (unsigned j=0;j<6;j++) {
        const enum htmlk_frame_owner kind=j<4?HTMLK_FRAME_TABLE:HTMLK_FRAME_DATA;
        if (!htmlk_frame_claim(&owners,kind,&phys[i][j]) ||
            phys[i][j]>HTMLK_M4_USER_PHYS_MASK ||
            hhdm>UINT64_MAX-phys[i][j]-HTMLK_PAGE_SIZE)
            fail("M4_D1_ALLOC_FAIL\n");
    }
    if (owners.live!=12 || phys[0][0]==phys[1][0] ||
        phys[0][5]==phys[1][5])
        fail("M4_D1_SHARED_FRAMES\n");
    volatile uint64_t *original=(volatile uint64_t *)(uintptr_t)(hhdm+old_cr3);
    task_init(0,htmlk_m4_d1_a_begin,htmlk_m4_d1_a_end,
              htmlk_m4_d1_a_loop,original);
    task_init(1,htmlk_m4_d1_b_begin,htmlk_m4_d1_b_end,
              htmlk_m4_d1_b_loop,original);
    active=0;ticks=switches=0;
#ifdef HTMLK_M4_D2_FAULT
    retired_a=false;
#endif
    for (unsigned i=0;i<2;i++) progress[i]=samples[i]=0;
#ifdef HTMLK_M4_D1_BAD_FRAME
    saved[1]->cs=0x08U;
    if (!valid(1,saved[1])) fail("M4_D1_BAD_FRAME_REJECTED\n");
    fail("M4_D1_BAD_FRAME_ACCEPTED\n");
#endif
    log_text("M4_D1_TWO_CPL3_CR3_READY\n");
    timer_start();
    htmlk_tss_set_rsp0(top(0));
    __asm__ volatile("mov %0,%%cr3"::"r"(phys[0][0]):"memory");
    htmlk_m4_d1_start(saved[0]);
    __asm__ volatile("cli":::"memory");
    if (cr3_now()!=old_cr3 || htmlk_tss_rsp0()!=old_rsp0 || switches<5)
        fail("M4_D1_MAIN_NOT_RESTORED\n");
#ifdef HTMLK_M4_D2_FAULT
    if (!retired_a || progress[0]!=2 || progress[1]!=5)
        fail("M4_D2_BAD_FAULT_RECOVERY_PROGRESS\n");
#else
    if (progress[0]!=STEPS || progress[1]!=STEPS)
        fail("M4_D1_BAD_PROGRESS\n");
#endif
    for (unsigned i=0;i<2;i++) for (unsigned j=0;j<6;j++) {
#ifdef HTMLK_M4_D2_FAULT
        if (i==0U && retired_a) continue; /* already reclaimed on IST2 */
#endif
        const enum htmlk_frame_owner kind=j<4?HTMLK_FRAME_TABLE:HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&owners,kind,phys[i][j]))
            fail("M4_D1_WRONG_OWNER_OR_DOUBLE_RELEASE\n");
    }
    if (owners.live!=0) fail("M4_D1_FRAME_LEAK\n");
    log_text("M4_D1_ALL_FRAMES_RECLAIMED\n");
}

#ifdef HTMLK_M4_D2_FAULT
/* Reached from a real #PF on IST2. Never return to A's poisoned ring3
 * context; switch to B's distinct CR3/RSP0 and return its saved IRET frame.
 * Unexpected faults have no privileged recovery capability. */
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_page_fault(
    uint64_t rip,uint64_t cs,uint64_t rsp,uint64_t ss,
    uint64_t error,uint64_t cr2) {
    if (active!=0U || retired_a ||
        progress[0]<2 || progress[1]<2 ||
        cr3_now()!=phys[0][0] || owners.live!=12 ||
        cs!=0x2bU || ss!=0x33U ||
        rsp!=HTMLK_M4_USER_STACK-16U ||
        rip!=HTMLK_M4_USER_BASE+
             (uint64_t)(htmlk_m4_d1_a_fault-htmlk_m4_d1_a_begin) ||
        error!=5U || cr2!=UINT64_C(0xffffffff80001000) ||
        !valid(1U,saved[1]))
        return NULL;
    retired_a=true;
    log_text("M4_D2_A_PF_ERROR_5\n");
    active=1U;
    htmlk_tss_set_rsp0(top(1U));
    __asm__ volatile("mov %0,%%cr3"::"r"(phys[1][0]):"memory");
    /* No CPU is referencing A's page tables after the full CR3 reload.
     * Still executing on the dedicated IST2 stack, never A's kstack. */
    for (unsigned j=0;j<6;j++) {
        const enum htmlk_frame_owner kind=j<4?HTMLK_FRAME_TABLE:HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&owners,kind,phys[0][j]))
            fail("M4_D2_WRONG_OWNER_OR_DOUBLE_FREE\n");
    }
    if (owners.live!=6 || !valid(1U,saved[1]))
        fail("M4_D2_B_CORRUPTED_AFTER_A_RECLAIM\n");
    log_text("M4_D2_A_RECLAIMED\n");
    return saved[1]; /* caller jumps to assembly IRET; no APIC EOI on #PF */
}
#endif
