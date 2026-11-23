/* M4-D: bounded, single-core x2APIC preemption of two real CPL3 loops.
 * NO FPU/SIMD/FS/GS, SMP, PCID, LA57, nested IRQ or production user loader. */
#include "user_preempt.h"
#include "user_preempt_policy.h"
#include "user_pages.h"
#include "page_pool.h"
#include "frame_owner.h"
#include "tss_ist.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

enum { D_TASKS=2, D_FRAMES=6, D_KSTACK_WORDS=2048, D_IRQ_LIMIT=384 };
#define D_CANARY UINT64_C(0xe219d11cc0ffee50)
#define D_READY_A UINT64_C(0x123456789abcdef0)
#define D_READY_B UINT64_C(0xfedcba9876543210)
#define D_APIC_BASE 0x1bU
#define D_APIC_EOI 0x80bU
#define D_APIC_TPR 0x808U
#define D_APIC_SVR 0x80fU
#define D_APIC_LVT 0x832U
#define D_APIC_DIVIDE 0x83eU
#define D_APIC_INIT 0x838U
static struct htmlk_frame_registry registry;
static uint64_t pages[D_TASKS][D_FRAMES], original_cr3, hhdm;
static uint64_t code_length[D_TASKS], last_counter[D_TASKS];
static uint64_t kstack[D_TASKS][D_KSTACK_WORDS] __attribute__((aligned(16)));
static struct htmlk_m4_d_irq_frame *saved[D_TASKS];
static unsigned steps[D_TASKS], current, irq_count, switches;
static bool faulted, survivor_advanced, exited;
static uint64_t peak_counter[D_TASKS];
uint64_t *htmlk_m4_main_stack;
static void debug(const char *s) {
    while (*s) __asm__ volatile ("outb %0,%1" : :
        "a"((uint8_t)*s++), "Nd"((uint16_t)0xe9));
}
__attribute__((noreturn))
static void fail(const char *reason) {
    __asm__ volatile ("cli" ::: "memory");
    debug(reason);
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0,%1" : :
        "a"((uint8_t)0x1c), "Nd"((uint16_t)0xf4)); /* error QEMU 57 */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static uint64_t msr_read(uint32_t reg) {
    uint32_t hi,lo;
    __asm__ volatile ("rdmsr" : "=a"(lo),"=d"(hi) : "c"(reg));
    return ((uint64_t)hi << 32) | lo;
}
static void msr_write(uint32_t reg,uint64_t v) {
    __asm__ volatile ("wrmsr" : : "c"(reg),"a"((uint32_t)v),
                    "d"((uint32_t)(v>>32)) : "memory");
}
static uint64_t cr3_read(void) {
    uint64_t out;
    __asm__ volatile ("mov %%cr3,%0" : "=r"(out));
    return out;
}
static void cr3_write(uint64_t cr3) {
    __asm__ volatile ("mov %0,%%cr3" : : "r"(cr3) : "memory");
}
static void apic_mask(void) {
    msr_write(D_APIC_LVT, 0x30040U);
    msr_write(D_APIC_INIT,0);
}
static void apic_start(bool initial) {
    __asm__ volatile ("cli" ::: "memory");
    if (initial) {
        uint32_t a,b,c,d;
        __asm__ volatile ("cpuid" : "=a"(a),"=b"(b),"=c"(c),"=d"(d) :
                          "a"(1U),"c"(0U));
        (void)a;(void)b;
        if (!(d & (1U << 9)) || !(c & (1U << 21)))
            fail("M4_D_X2APIC_UNSUPPORTED\n");
        const uint64_t base = msr_read(D_APIC_BASE);
        if (!(base & (1ULL<<11))) fail("M4_D_APIC_DISABLED\n");
        msr_write(D_APIC_BASE,base | (1ULL<<10));
        if ((msr_read(D_APIC_BASE) & (3ULL<<10))!=(3ULL<<10))
            fail("M4_D_X2APIC_NOT_ACTIVE\n");
        __asm__ volatile ("outb %0,%1" : : "a"((uint8_t)0xff),"Nd"((uint16_t)0x21));
        __asm__ volatile ("outb %0,%1" : : "a"((uint8_t)0xff),"Nd"((uint16_t)0xa1));
        msr_write(D_APIC_TPR,0);
        msr_write(D_APIC_SVR,0x1ffU);
        msr_write(D_APIC_DIVIDE,3U);
    }
#ifdef HTMLK_M4_D_TIMER_MASK
    msr_write(D_APIC_LVT,0x30040U);
#else
    msr_write(D_APIC_LVT,0x20040U);
#endif
    msr_write(D_APIC_INIT,1000000U);
}
static uint64_t user_word(unsigned task,unsigned end_offset) {
    if (task>=D_TASKS || end_offset>4096U || end_offset<8U)
        fail("M4_D_BAD_USER_STACK_OFFSET\n");
    volatile uint64_t *p = (volatile uint64_t *)(uintptr_t)(
        hhdm + pages[task][5] + HTMLK_PAGE_SIZE - end_offset);
    return *p;
}
static void set_user_word(unsigned task,unsigned end_offset,uint64_t value) {
    volatile uint64_t *p = (volatile uint64_t *)(uintptr_t)(
        hhdm + pages[task][5] + HTMLK_PAGE_SIZE - end_offset);
    *p=value;
}
static bool saved_on_stack(unsigned task, const struct htmlk_m4_d_irq_frame *f) {
    if (task>=D_TASKS || !f) return false;
    uintptr_t at=(uintptr_t)f;
    uintptr_t low=(uintptr_t)&kstack[task][64U];
    uintptr_t high=(uintptr_t)&kstack[task][D_KSTACK_WORDS];
    return at>=low && at<=high-sizeof(*f) &&
        (at & 7U)==0 && kstack[task][0]==D_CANARY;
}
static uint64_t rsp0(unsigned task) {
    return (uint64_t)(uintptr_t)&kstack[task][D_KSTACK_WORDS];
}
static bool valid_running(unsigned task, struct htmlk_m4_d_irq_frame *f) {
    return saved_on_stack(task,f) &&
        htmlk_m4_d_user_frame_valid(f->rip,f->cs,f->rflags,
            f->rsp,f->ss,cr3_read(),pages[task][0],code_length[task]) &&
        htmlk_m4_tss_get_rsp0()==rsp0(task);
}
static bool valid_target(unsigned task) {
    if (task>=D_TASKS || pages[0][0]==pages[1][0]) return false;
    struct htmlk_m4_d_irq_frame *f=saved[task];
    return saved_on_stack(task,f) &&
        htmlk_m4_d_user_frame_valid(f->rip,f->cs,f->rflags,
            f->rsp,f->ss,pages[task][0],pages[task][0],code_length[task]);
}
static void inspect_counter(unsigned task, const struct htmlk_m4_d_irq_frame *f) {
    const uint64_t ready=user_word(task,40U);
    const uint64_t expected=task==0 ? D_READY_A : D_READY_B;
    if (ready!=expected) {
        if (irq_count>32U) fail("M4_D_RING3_NEVER_INITIALIZED\n");
        return; /* interrupt landed before user had initialized registers */
    }
    const uint64_t r12=task==0 ? UINT64_C(0x1111222233334444) :
                                 UINT64_C(0x1111222233335555);
    const uint64_t r13=task==0 ? UINT64_C(0xaaaabbbbccccdddd) :
                                 UINT64_C(0xaaaabbbbccccbeee);
    const uint64_t base=task==0U ? 0xa0U : 0xb0U;
    if (f->r12!=r12 || f->r13!=r13 || f->rax!=expected ||
        f->rbx!=base+1U || f->rcx!=base+2U ||
        f->rdx!=base+3U || f->rsi!=base+4U ||
        f->rdi!=base+5U || f->rbp!=base+6U ||
        f->r8!=base+7U || f->r9!=base+8U ||
        f->r10!=base+9U || f->r11!=base+10U ||
        f->r14!=base+11U || f->r15!=base+12U)
        fail("M4_D_ALL_GPR_PRESERVATION_FAILED\n");
    const uint64_t count=user_word(task,24U);
    if (count<=last_counter[task])
        fail("M4_D_USER_DID_NOT_EXECUTE\n");
    last_counter[task]=count;
    if (count>peak_counter[task]) peak_counter[task]=count;
    if (steps[task]<3U) {
        const char *markers[2][3]={
            {"M4_D_A_0\n","M4_D_A_1\n","M4_D_A_2\n"},
            {"M4_D_B_0\n","M4_D_B_1\n","M4_D_B_2\n"}
        };
        debug(markers[task][steps[task]++]);
    } else if (faulted && task==1U && !survivor_advanced) {
        survivor_advanced=true;
        debug("M4_D_B_SURVIVED_FAULT\n");
    }
}
uint64_t *htmlk_m4_on_timer_irq(uint64_t *irq_stack) {
    struct htmlk_m4_d_irq_frame *f=(struct htmlk_m4_d_irq_frame *)irq_stack;
    if (current>=D_TASKS || !valid_running(current,f))
        fail("M4_D_UNTRUSTED_INTERRUPT_FRAME\n");
    if (++irq_count>D_IRQ_LIMIT)
        fail("M4_D_SCHEDULER_BUDGET_EXCEEDED\n");
    saved[current]=f;
    inspect_counter(current,f);
    if (!faulted && steps[0]>=3U && steps[1]>=3U) {
        set_user_word(0,32U,1U); /* A faults on its OWN next user instruction */
    }
    if (faulted && current==1U) {
        if (survivor_advanced) set_user_word(1,32U,1U);
        msr_write(D_APIC_EOI,0);
        return irq_stack;
    }
    const unsigned next=current^1U;
    if (!valid_target(next)) fail("M4_D_INVALID_NEXT_TASK_CONTEXT\n");
    current=next;
    ++switches;
    htmlk_m4_tss_set_rsp0(rsp0(next));
    cr3_write(pages[next][0]);
    msr_write(D_APIC_EOI,0);
    return (uint64_t *)saved[next];
}
bool htmlk_m4_d_accept_fault(unsigned vec, uint64_t rip, uint64_t cs,
    uint64_t flags,uint64_t rsp,uint64_t ss,uint64_t err,uint64_t cr2) {
    if (current!=0U || faulted || !saved_on_stack(0,saved[0]) ||
        !htmlk_m4_d_fault_valid(current,vec,err,cr2,rip,cs,flags,
            rsp,ss,cr3_read(),pages[0][0],code_length[0],
            steps[0],steps[1])) return false;
    faulted=true;
    debug("M4_D_A_USER_PF_CONTAINED\n");
    return true;
}
__attribute__((noreturn)) void htmlk_m4_d_retire_fault(void) {
    apic_mask();
    cr3_write(original_cr3);
    htmlk_m4_d_return_main();
}
__attribute__((noreturn))
void htmlk_m4_d_user_syscall(struct htmlk_m4_d_irq_frame *f) {
    if (current!=1U || !faulted || !survivor_advanced || !f ||
        f->rax!=1U || f->rdi!=0U || user_word(1,32U)!=1U ||
        !valid_running(1,f))
        fail("M4_D_USER_SYSCALL_DENIED\n");
    exited=true;
    debug("M4_D_B_CPL3_EXIT_OK\n");
    apic_mask();
    cr3_write(original_cr3);
    htmlk_m4_d_return_main();
}
static void init_task(unsigned task, const unsigned char *start,
    const unsigned char *end,volatile uint64_t *original) {
    uintptr_t first=(uintptr_t)start,last=(uintptr_t)end;
    if (last<=first || last-first>HTMLK_PAGE_SIZE)
        fail("M4_D_USER_IMAGE_SIZE_INVALID\n");
    code_length[task]=(uint64_t)(last-first);
    volatile uint64_t *tables[4];
    for (unsigned i=0;i<4U;++i)
        tables[i]=(volatile uint64_t *)(uintptr_t)(hhdm+pages[task][i]);
    volatile uint8_t *text_page=(volatile uint8_t *)(uintptr_t)(
        hhdm+pages[task][4]);
    volatile uint8_t *stack_page=(volatile uint8_t *)(uintptr_t)(
        hhdm+pages[task][5]);
    for (unsigned i=0;i<512U;++i)
        tables[0][i]=original[i]&~HTMLK_M4_USER_BIT;
    for (unsigned i=0;i<4096U;++i) {
        text_page[i]=i<code_length[task] ? start[i] : 0U;
        stack_page[i]=0;
    }
    if (!htmlk_m4_user_wire(tables[0],tables[1],tables[2],tables[3],
                           pages[task]))
        fail("M4_D_PAGE_PERMISSION_REJECTED\n");
    kstack[task][0]=D_CANARY;
    const uintptr_t top=(uintptr_t)&kstack[task][D_KSTACK_WORDS];
    struct htmlk_m4_d_irq_frame *f=(struct htmlk_m4_d_irq_frame *)(
        top-sizeof(struct htmlk_m4_d_irq_frame));
    volatile uint64_t *raw=(volatile uint64_t *)f;
    for (unsigned i=0;i<sizeof(*f)/sizeof(uint64_t);++i) raw[i]=0;
    f->rip=HTMLK_M4_USER_BASE;
    f->cs=HTMLK_M4_D_USER_CS;
    f->rflags=0x202U;
    f->rsp=HTMLK_M4_USER_STACK-16U;
    f->ss=HTMLK_M4_D_USER_SS;
    saved[task]=f;
    if (!valid_target(task))
        fail("M4_D_INVALID_SYNTHETIC_IRET_FRAME\n");
}
static void release(unsigned task) {
    if (cr3_read()!=original_cr3 || task>=D_TASKS)
        fail("M4_D_CANNOT_RELEASE_ACTIVE_CR3\n");
    for (unsigned i=0;i<D_FRAMES;++i) {
        const enum htmlk_frame_owner owner=i<4U ?
            HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
        if (!htmlk_frame_release(&registry,owner,pages[task][i]))
            fail("M4_D_OWNER_DOUBLE_RELEASE\n");
    }
}
void htmlk_m4_user_preempt_probe(const struct limine_memmap_response *map,
    const struct limine_hhdm_response *hhdm_response) {
    __asm__ volatile ("cli" ::: "memory");
    if (!map || !map->entries || !map->entry_count ||
        map->entry_count>HTMLK_MAX_MEMORY_REGIONS || !hhdm_response)
        fail("M4_D_MISSING_BOOT_MAP\n");
    uint64_t cr4;
    __asm__ volatile ("mov %%cr4,%0" : "=r"(cr4));
    if (cr4 & ((UINT64_C(1)<<12)|(UINT64_C(1)<<17)))
        fail("M4_D_PCID_LA57_UNSUPPORTED\n");
    struct htmlk_phys_range regions[HTMLK_MAX_MEMORY_REGIONS];
    for (uint64_t i=0;i<map->entry_count;++i) {
        if (!map->entries[i]) fail("M4_D_NULL_BOOT_REGION\n");
        regions[i].base=map->entries[i]->base;
        regions[i].length=map->entries[i]->length;
        regions[i].type=map->entries[i]->type;
    }
    struct htmlk_page_pool pool={0};
    if (!htmlk_page_pool_init(regions,map->entry_count,&pool) ||
        !htmlk_frames_init(&registry,&pool))
        fail("M4_D_USABLE_FRAME_POOL_MISSING\n");
    original_cr3=cr3_read();
    hhdm=hhdm_response->offset;
    const uint64_t cr3_phys=original_cr3&HTMLK_M4_USER_PHYS_MASK;
    if (original_cr3!=cr3_phys || !cr3_phys || !hhdm ||
        (hhdm&4095U) || hhdm>UINT64_MAX-cr3_phys-4096U)
        fail("M4_D_CR3_HHDM_UNSAFE\n");
    for (unsigned task=0;task<D_TASKS;++task) {
        for (unsigned i=0;i<D_FRAMES;++i) {
            const enum htmlk_frame_owner owner=i<4U ?
                HTMLK_FRAME_TABLE : HTMLK_FRAME_DATA;
            if (!htmlk_frame_claim(&registry,owner,&pages[task][i]) ||
                !pages[task][i] ||
                (pages[task][i]&~HTMLK_M4_USER_PHYS_MASK) ||
                hhdm>UINT64_MAX-pages[task][i]-4096U)
                fail("M4_D_OWNED_FRAME_EXHAUSTED\n");
        }
    }
    if (registry.live!=12 || pages[0][0]==pages[1][0] ||
        pages[0][5]==pages[1][5])
        fail("M4_D_SHARED_PAGE_OWNER\n");
    volatile uint64_t *orig=(volatile uint64_t *)(uintptr_t)(
        hhdm+original_cr3);
    init_task(0,htmlk_m4_d_a_begin,htmlk_m4_d_a_end,orig);
    init_task(1,htmlk_m4_d_b_begin,htmlk_m4_d_b_end,orig);
#ifdef HTMLK_M4_D_BAD_FRAME
    saved[1]->cs=0x08U;
    if (!valid_target(1)) fail("M4_D_BAD_USER_FRAME_REJECTED\n");
    fail("M4_D_BAD_USER_FRAME_ACCEPTED\n");
#endif
#ifdef HTMLK_M4_D_WRONG_CR3
    pages[1][0]=pages[0][0];
    if (!valid_target(1)) fail("M4_D_BAD_CR3_REJECTED\n");
    fail("M4_D_BAD_CR3_ACCEPTED\n");
#endif
    debug("M4_D_TWO_USER_CR3_READY\n");
    apic_start(true);
    debug("M4_D_X2APIC_READY\n");
    current=0;
    htmlk_m4_tss_set_rsp0(rsp0(0));
    cr3_write(pages[0][0]);
    htmlk_m4_enter_first((uint64_t *)saved[0]);
    __asm__ volatile ("cli" ::: "memory");
    if (!faulted || current!=0 || cr3_read()!=original_cr3 ||
        steps[0]<3U || steps[1]<3U || switches<5U ||
        user_word(0,40U)!=D_READY_A ||
        user_word(1,40U)!=D_READY_B)
        fail("M4_D_A_FAULT_RESUME_FAILED\n");
    release(0);
    if (registry.live!=6)
        fail("M4_D_A_FRAME_LEAK\n");
    debug("M4_D_A_FRAMES_RELEASED\n");
    current=1;
    htmlk_m4_tss_set_rsp0(rsp0(1));
    apic_start(false);
    cr3_write(pages[1][0]);
    htmlk_m4_enter_first((uint64_t *)saved[1]);
    __asm__ volatile ("cli" ::: "memory");
    if (!exited || !survivor_advanced || cr3_read()!=original_cr3)
        fail("M4_D_B_EXIT_RESUME_FAILED\n");
    release(1);
    if (registry.live!=0)
        fail("M4_D_FINAL_FRAME_LEAK\n");
    debug("M4_D_ISOLATED_PREEMPTION_PASS\n");
}
