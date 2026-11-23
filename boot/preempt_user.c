/* M4-D: one CPU, two never-yielding ring3 tasks, distinct CR3+RSP0.
 * Local x2APIC interrupt preempts each running user task; real user #PF
 * retires A while B keeps running from its previously saved IRQ stack.
 * This is NOT a generic process runtime, SMP, FPU or user syscall ABI.
 */
#include "preempt_user.h"
#include "limine.h"
#include "user_pages.h"
#include "page_pool.h"
#include "frame_owner.h"
#include "tss_ist.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
enum { BAD=0, SURVIVOR=1, OWNED=6, STACK_BYTES=16384, IRQ_LIMIT=96 };
#define APIC_BASE 0x1bU
#define APIC_EOI 0x80bU
#define APIC_SVR 0x80fU
#define APIC_TPR 0x808U
#define APIC_TIMER 0x832U
#define APIC_COUNT 0x838U
#define APIC_DIVIDE 0x83eU
#define USER_CS UINT64_C(0x2b)
#define USER_SS UINT64_C(0x33)
#define A_RBX HTMLK_M4_D_A_RBX
#define B_RBX HTMLK_M4_D_B_RBX
#define A_R12 HTMLK_M4_D_A_R12
#define B_R12 HTMLK_M4_D_B_R12
#define A_R10 HTMLK_M4_D_A_R10
#define B_R10 HTMLK_M4_D_B_R10
#define STACK_CANARY UINT64_C(0x6d34442c4f534b21)

static struct htmlk_frame_registry registry;
static uint64_t phys[HTMLK_M4_D_TASKS][OWNED];
static uint64_t image_size[HTMLK_M4_D_TASKS];
static uint64_t hhdm, original_cr3;
static uint64_t *saved[HTMLK_M4_D_TASKS];
uint64_t *htmlk_m4_d_main_rsp;
static volatile uint64_t latest[HTMLK_M4_D_TASKS];
static unsigned progress[HTMLK_M4_D_TASKS];
static unsigned current_task = BAD;
static unsigned ticks, switches, fault_count;
static uint64_t retired_a_counter;
static bool armed, retired, finalized;
static uint8_t kstack[HTMLK_M4_D_TASKS][STACK_BYTES]
    __attribute__((aligned(16)));

static void out(uint16_t port,uint8_t value) {
    __asm__ volatile ("outb %0,%1" : : "a"(value),"Nd"(port) : "memory");
}
static void log_text(const char *s) {
    while (*s) out(0xe9U,(uint8_t)*s++);
}
__attribute__((noreturn)) static void fail(const char *s) {
    __asm__ volatile ("cli" ::: "memory");
    log_text(s);
#ifdef HTMLK_QEMU_TEST_EXIT
    out(0xf4U,0x1bU); /* QEMU exit 55 */
#endif
    for (;;) __asm__ volatile ("cli;hlt");
}
static uint64_t cr3(void) {
    uint64_t v;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(v));
    return v;
}
static uint64_t rdmsr(uint32_t msr) {
    uint32_t lo,hi;
    __asm__ volatile ("rdmsr":"=a"(lo),"=d"(hi):"c"(msr));
    return ((uint64_t)hi << 32) | lo;
}
static void wrmsr(uint32_t msr,uint64_t value) {
    __asm__ volatile ("wrmsr"::"c"(msr),"a"((uint32_t)value),
                      "d"((uint32_t)(value>>32)):"memory");
}
static void timer_init(void) {
    uint32_t eax,ebx,ecx,edx;
    __asm__ volatile ("cpuid":"=a"(eax),"=b"(ebx),"=c"(ecx),
                      "=d"(edx):"a"(1U),"c"(0U));
    (void)eax;(void)ebx;
    if ((ecx & (1U<<21))==0 || (edx & (1U<<9))==0)
        fail("M4_D_X2APIC_UNSUPPORTED\n");
    const uint64_t base=rdmsr(APIC_BASE);
    if ((base & (1ULL<<11))==0)
        fail("M4_D_APIC_DISABLED\n");
    wrmsr(APIC_BASE,base|(1ULL<<10));
    if ((rdmsr(APIC_BASE)&(3ULL<<10))!=(3ULL<<10))
        fail("M4_D_APIC_NOT_ENABLED\n");
    out(0x21U,0xffU);out(0xa1U,0xffU);
    wrmsr(APIC_TPR,0);wrmsr(APIC_SVR,0x1ffU);
    wrmsr(APIC_DIVIDE,3U);
#ifdef HTMLK_M4_D_TIMER_MASK
    wrmsr(APIC_TIMER,0x30040U);
#else
    wrmsr(APIC_TIMER,0x20040U);
#endif
    wrmsr(APIC_COUNT,1000000U); /* emulator specific, not 100 Hz */
    log_text("M4_D_TIMER_READY\n");
}
static void timer_stop(void) {
    wrmsr(APIC_TIMER,0x30040U);
    wrmsr(APIC_COUNT,0);
}
static bool valid_saved(unsigned task,const struct htmlk_m4_d_frame *f) {
    if (task>=HTMLK_M4_D_TASKS || !f) return false;
    const uintptr_t addr=(uintptr_t)f;
    const uintptr_t bottom=(uintptr_t)&kstack[task][256];
    const uintptr_t top=(uintptr_t)&kstack[task][STACK_BYTES];
    return addr>=bottom && addr<=top-sizeof(*f) &&
        (addr & 7U)==0 &&
        htmlk_m4_d_arch_frame_valid(f,task,image_size[task]) &&
        *(volatile uint64_t *)&kstack[task][0]==STACK_CANARY;
}
static volatile uint64_t *counter(unsigned task) {
    return (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][5] + HTMLK_PAGE_SIZE - 24U);
}
static volatile uint64_t *fault_flag(unsigned task) {
    return (volatile uint64_t *)(uintptr_t)(
        hhdm + phys[task][5] + HTMLK_PAGE_SIZE - 32U);
}
static void init_task(unsigned task,
                      const unsigned char *start,const unsigned char *end,
                      volatile uint64_t *original) {
    const uintptr_t begin=(uintptr_t)start,finish=(uintptr_t)end;
    if (finish<=begin || finish-begin>HTMLK_PAGE_SIZE)
        fail("M4_D_IMAGE_TOO_LARGE\n");
    image_size[task]=finish-begin;
    volatile uint64_t *root=(volatile uint64_t *)(uintptr_t)(hhdm+phys[task][0]);
    volatile uint64_t *pdpt=(volatile uint64_t *)(uintptr_t)(hhdm+phys[task][1]);
    volatile uint64_t *pd=(volatile uint64_t *)(uintptr_t)(hhdm+phys[task][2]);
    volatile uint64_t *pt=(volatile uint64_t *)(uintptr_t)(hhdm+phys[task][3]);
    volatile uint8_t *code=(volatile uint8_t *)(uintptr_t)(hhdm+phys[task][4]);
    volatile uint8_t *stack=(volatile uint8_t *)(uintptr_t)(hhdm+phys[task][5]);
    for(unsigned i=0;i<512;++i)
        root[i]=original[i]&~HTMLK_M4_USER_BIT;
    for(unsigned i=0;i<HTMLK_PAGE_SIZE;++i){
        code[i]=i<image_size[task]?start[i]:0U;
        stack[i]=0U;
    }
    if (!htmlk_m4_user_wire(root,pdpt,pd,pt,phys[task]) ||
        (root[HTMLK_M4_USER_SLOT]&7U)!=7U ||
        (pt[0]&7U)!=5U || (pt[1]&7U)!=7U)
        fail("M4_D_USER_PTE_INVALID\n");
    const uintptr_t top=(uintptr_t)&kstack[task][STACK_BYTES];
    struct htmlk_m4_d_frame *f=(struct htmlk_m4_d_frame *)(
        top-sizeof(struct htmlk_m4_d_frame));
    for(unsigned i=0;i<sizeof(*f)/8U;++i)
        ((uint64_t *)f)[i]=0;
    f->rip=HTMLK_M4_USER_BASE;
    f->cs=USER_CS;f->ss=USER_SS;f->rflags=0x202U;
    f->rsp=HTMLK_M4_USER_STACK-16U;
    f->rbx=task==BAD?A_RBX:B_RBX;
    f->r12=task==BAD?A_R12:B_R12;
    f->r10=task==BAD?A_R10:B_R10;
    f->r13=task==BAD?A_RBX:B_RBX;
    *(uint64_t *)&kstack[task][0]=STACK_CANARY;
    saved[task]=(uint64_t *)f;
    if (!valid_saved(task,f))
        fail("M4_D_BAD_INITIAL_TASK_FRAME\n");
}
static void release_task(unsigned task) {
    if (task>=HTMLK_M4_D_TASKS || cr3()!=original_cr3)
        fail("M4_D_RELEASE_WITH_ACTIVE_USER_CR3\n");
    for(unsigned i=0;i<OWNED;++i) {
        const enum htmlk_frame_owner owner=
            i<4U?HTMLK_FRAME_TABLE:HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&registry,owner,phys[task][i]))
            fail("M4_D_FRAME_DOUBLE_FREE\n");
    }
}
static bool htmlk_m4_d_set_rsp0(unsigned task) {
    return task<HTMLK_M4_D_TASKS && htmlk_tss_user_set_rsp0(
        (uint64_t)(uintptr_t)&kstack[task][STACK_BYTES]);
}
static bool htmlk_m4_d_rsp0_matches(unsigned task) {
    return task<HTMLK_M4_D_TASKS && htmlk_tss_user_rsp0()==
        (uint64_t)(uintptr_t)&kstack[task][STACK_BYTES];
}
static void use_task(unsigned task) {
    if(task>=HTMLK_M4_D_TASKS ||
       !htmlk_m4_d_set_rsp0(task) ||
       !valid_saved(task,(struct htmlk_m4_d_frame *)saved[task]))
        fail("M4_D_BAD_NEXT_TASK_CONTEXT\n");
    current_task=task;
    __asm__ volatile ("mov %0,%%cr3"::"r"(phys[task][0]):"memory");
}
static void print_progress(unsigned task,unsigned n) {
    log_text(task==BAD?"M4_D_A_":"M4_D_B_");
    out(0xe9U,(uint8_t)('0'+n));out(0xe9U,(uint8_t)'\n');
}
uint64_t *htmlk_m4_d_on_timer(struct htmlk_m4_d_frame *f) {
    if (current_task>=HTMLK_M4_D_TASKS ||
        (retired && current_task==BAD) ||
        cr3()!=phys[current_task][0] ||
        !htmlk_m4_d_rsp0_matches(current_task) ||
        !valid_saved(current_task,f))
        fail("M4_D_INVALID_IRQ_CONTEXT\n");
    saved[current_task]=(uint64_t *)f;
    if (++ticks>IRQ_LIMIT)
        fail("M4_D_IRQ_TICK_LIMIT\n");
    const unsigned running=current_task;
    const uint64_t now=*counter(running);
    if (now<=latest[running])
        fail("M4_D_USER_NO_REAL_PROGRESS\n");
    latest[running]=now;
    if (progress[running]<3U) {
        print_progress(running,progress[running]);
        ++progress[running];
    } else if (running==SURVIVOR && retired && progress[SURVIVOR]<5U) {
        log_text(progress[SURVIVOR]==3U
                 ?"M4_D_B_AFTER_FAULT_3\n"
                 :"M4_D_B_AFTER_FAULT_4\n");
        ++progress[SURVIVOR];
    }
#ifdef HTMLK_M4_D_UNEXPECTED_B_GP
    if (retired && running==SURVIVOR && progress[SURVIVOR]==4U)
        *fault_flag(SURVIVOR)=1U;
#endif
    if (retired && progress[SURVIVOR]>=5U) {
        if (!armed || fault_count!=1U || switches<6U ||
            retired_a_counter==0 || *counter(SURVIVOR)==0)
            fail("M4_D_BAD_FINAL_PROGRESS\n");
        timer_stop();
        wrmsr(APIC_EOI,0);
        finalized=true;
        __asm__ volatile ("mov %0,%%cr3"::"r"(original_cr3):"memory");
        log_text("M4_D_RING3_PREEMPT_PASS\n");
        return NULL;
    }
    unsigned next=retired?SURVIVOR:(running^1U);
    if (!retired && progress[BAD]>=3U && progress[SURVIVOR]>=3U &&
        !armed && running==SURVIVOR) {
        *fault_flag(BAD)=1U; /* A faults only after both had real CPU progress */
        armed=true;
    }
    if (next!=running) ++switches;
    wrmsr(APIC_EOI,0);
    if (next!=running) use_task(next);
    return saved[next];
}
bool htmlk_m4_d_accept_fault(unsigned vector,uint64_t rip,uint64_t cs,
                            uint64_t rsp,uint64_t ss,uint64_t error,
                            uint64_t cr2) {
    if (retired || !armed || current_task!=BAD || fault_count!=0U ||
        cr3()!=phys[BAD][0] || cs!=USER_CS || ss!=USER_SS ||
        rip<HTMLK_M4_USER_BASE ||
        rip-HTMLK_M4_USER_BASE>=image_size[BAD] ||
        rsp<=HTMLK_M4_USER_STACK-HTMLK_PAGE_SIZE ||
        rsp>HTMLK_M4_USER_STACK ||
        progress[BAD]<3U || progress[SURVIVOR]<3U ||
        *fault_flag(BAD)!=1U) return false;
#ifdef HTMLK_M4_D_GP_FAULT
    if (vector!=13U || error!=0U || cr2!=0U) return false;
    log_text("M4_D_A_CPU_GP_0\n");
#elif defined(HTMLK_M4_D_RO_FAULT)
    if (vector!=14U || error!=7U || cr2!=HTMLK_M4_USER_BASE) return false;
    log_text("M4_D_A_CPU_PF_7\n");
#else
    if (vector!=14U || error!=5U ||
        cr2!=UINT64_C(0xffffffff80001000)) return false;
    log_text("M4_D_A_CPU_PF_5\n");
#endif
    retired_a_counter=*counter(BAD);
    ++fault_count;
    retired=true;
    __asm__ volatile ("cli;mov %0,%%cr3"::"r"(original_cr3):"memory");
    release_task(BAD);
    if (registry.live!=6U)
        fail("M4_D_A_FRAME_LEAK\n");
    log_text("M4_D_A_RECLAIMED\n");
    use_task(SURVIVOR); /* switch CR3 and TSS.RSP0 while on intact IST stack */
    if (!valid_saved(SURVIVOR,(struct htmlk_m4_d_frame *)saved[SURVIVOR]))
        fail("M4_D_BAD_SURVIVOR_IRQ_FRAME\n");
    htmlk_m4_d_resume(saved[SURVIVOR]); /* never return to dead A's frame */
    __builtin_unreachable();
}
void htmlk_m4_d_probe(const struct limine_memmap_response *map,
                      const struct limine_hhdm_response *response) {
    __asm__ volatile ("cli":::"memory");
    if (!map || !map->entries || !response ||
        map->entry_count==0 || map->entry_count>HTMLK_MAX_MEMORY_REGIONS)
        fail("M4_D_NO_MEMORY_MAP\n");
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4,%0":"=r"(cr4));
    if (cr4 & ((1ULL<<12)|(1ULL<<17)))
        fail("M4_D_LA57_PCID_UNSUPPORTED\n");
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for(uint64_t i=0;i<map->entry_count;++i) {
        if (!map->entries[i]) fail("M4_D_NULL_REGION\n");
        regions[i].base=map->entries[i]->base;
        regions[i].length=map->entries[i]->length;
        regions[i].type=map->entries[i]->type;
    }
    struct htmlk_page_pool pool={0};
    if (!htmlk_page_pool_init(regions,map->entry_count,&pool) ||
        !htmlk_frames_init(&registry,&pool))
        fail("M4_D_NO_FRAME_POOL\n");
    original_cr3=cr3();
    hhdm=response->offset;
    if ((original_cr3 & ~HTMLK_M4_USER_PHYS_MASK)!=0 ||
        !original_cr3 || !hhdm || (hhdm & (HTMLK_PAGE_SIZE-1U)) ||
        hhdm>UINT64_MAX-original_cr3-HTMLK_PAGE_SIZE)
        fail("M4_D_BAD_HHDM\n");
    for(unsigned t=0;t<HTMLK_M4_D_TASKS;++t)
        for(unsigned i=0;i<OWNED;++i) {
            const enum htmlk_frame_owner owner=
                i<4U?HTMLK_FRAME_TABLE:HTMLK_FRAME_DATA;
            if (!htmlk_frame_claim(&registry,owner,&phys[t][i]) ||
                phys[t][i]>HTMLK_M4_USER_PHYS_MASK ||
                hhdm>UINT64_MAX-phys[t][i]-HTMLK_PAGE_SIZE)
                fail("M4_D_OWNED_FRAME_ALLOCATION\n");
        }
    volatile uint64_t *original=(volatile uint64_t *)(uintptr_t)(
        hhdm+original_cr3);
    init_task(BAD,htmlk_m4_d_bad_begin,htmlk_m4_d_bad_end,original);
    init_task(SURVIVOR,htmlk_m4_d_good_begin,htmlk_m4_d_good_end,original);
    if(registry.live!=12U || phys[BAD][0]==phys[SURVIVOR][0] ||
       phys[BAD][4]==phys[SURVIVOR][4] ||
       phys[BAD][5]==phys[SURVIVOR][5])
        fail("M4_D_SHARED_USER_PAGES\n");
#ifdef HTMLK_M4_D_BAD_FRAME
    if(valid_saved(BAD,(struct htmlk_m4_d_frame *)(
        (uintptr_t)saved[BAD]+1U)))
        fail("M4_D_MISALIGNED_FRAME_ACCEPTED\n");
    fail("M4_D_MISALIGNED_FRAME_REJECTED\n");
#endif
    log_text("M4_D_USER_ROOTS_READY\n");
    timer_init();
    use_task(BAD);
    htmlk_m4_d_enter(saved[BAD]);
    __asm__ volatile ("cli":::"memory");
    if(!finalized || !retired || fault_count!=1U ||
       cr3()!=original_cr3 || registry.live!=6U)
        fail("M4_D_MAIN_RESTORE_INVALID\n");
    release_task(SURVIVOR);
    if(registry.live!=0U)
        fail("M4_D_REMAINING_FRAME_LEAK\n");
    log_text("M4_D_NO_FRAME_LEAK\n");
}
