#include "user_preempt_frame.h"
#include "user_pages.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t stack[256] __attribute__((aligned(16)));
#define BX UINT64_C(0x123456789abcdef0)
#define R12 UINT64_C(0x76543210fedcba98)
int main(void) {
    struct htmlk_m4_d1_irq_frame *f=(void *)
        ((uint8_t *)&stack[256]-sizeof(struct htmlk_m4_d1_irq_frame));
    memset(stack,0,sizeof stack);
    f->rip=HTMLK_M4_USER_BASE;
    f->cs=0x2b;f->ss=0x33;f->rsp=HTMLK_M4_USER_STACK-16;
    f->rflags=0x202;
    const uintptr_t low=(uintptr_t)&stack[8],high=(uintptr_t)&stack[256];
#define OK htmlk_m4_d1_frame_guard(f,low,high,200,40,BX,R12)
    assert(OK);
    f->cs=0x08;assert(!OK);f->cs=0x2b;
    f->ss=0x10;assert(!OK);f->ss=0x33;
    f->rflags=0x02;assert(!OK);f->rflags=0x202;
    f->rflags=0x3202;assert(!OK);f->rflags=0x202; /* IOPL3 forbidden */
    f->rflags=0x4202;assert(!OK);f->rflags=0x202; /* NT forbidden */
    f->rflags=0x20202;assert(!OK);f->rflags=0x202; /* VM forbidden */
    f->rsp=HTMLK_M4_USER_BASE;assert(!OK);
    f->rsp=HTMLK_M4_USER_STACK-16;
    f->rip=HTMLK_M4_USER_BASE+200;assert(!OK);
    f->rip=HTMLK_M4_USER_BASE+40;assert(!OK);
    f->rbx=BX;f->r12=R12;assert(OK);
    f->rbx^=1;assert(!OK);f->rbx=BX;assert(OK);
    f->r12^=1;assert(!OK);f->r12=R12;assert(OK);
    assert(!htmlk_m4_d1_frame_guard(f,low,high,0,0,BX,R12));
    assert(!htmlk_m4_d1_frame_guard(f,low,high,4097,0,BX,R12));
    assert(!htmlk_m4_d1_frame_guard(f,low,high,200,200,BX,R12));
    assert(!htmlk_m4_d1_frame_guard(f,high,low,200,40,BX,R12));
    assert(!htmlk_m4_d1_frame_guard((void *)((uintptr_t)f+1),
                                   low,high,200,40,BX,R12));
    assert(!htmlk_m4_d1_frame_guard((void *)(uintptr_t)1,
                                   low,high,200,40,BX,R12));
    puts("M4-D PURE IRQ FRAME GUARD PASS");
    return 0;
}
