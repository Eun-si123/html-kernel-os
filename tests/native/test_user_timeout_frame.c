#include "user_timeout_frame.h"
#include "user_pages.h"
#include <assert.h>
#include <stdint.h>
#include <string.h>

static _Alignas(16) uint8_t kstack[16384];
int main(void) {
    const uint64_t top=(uint64_t)(uintptr_t)(kstack+sizeof(kstack));
    struct htmlk_m4_d1_irq_frame *f=(void *)(uintptr_t)(top-sizeof(*f));
    memset(f,0,sizeof(*f));
    f->cs=0x2bU;
    f->ss=0x33U;
    f->rip=HTMLK_M4_USER_BASE+5U;
    f->rsp=HTMLK_M4_USER_STACK-16U;
    f->rflags=0x202U;
    const uint64_t root=UINT64_C(0x12345000);
#define ACCEPT() htmlk_m5_timeout_frame_valid(f,top,45U,root,root)
    assert(ACCEPT());
    f->cs=0x08U;assert(!ACCEPT());f->cs=0x2bU;
    f->ss=0x10U;assert(!ACCEPT());f->ss=0x33U;
    f->rflags=0x2U;assert(!ACCEPT());f->rflags=0x202U;
    f->rflags|=3ULL<<12;assert(!ACCEPT());f->rflags=0x202U;
    f->rflags|=1ULL<<14;assert(!ACCEPT());f->rflags=0x202U;
    f->rflags|=1ULL<<17;assert(!ACCEPT());f->rflags=0x202U;
    f->rip=HTMLK_M4_USER_BASE+45U;assert(!ACCEPT());f->rip=HTMLK_M4_USER_BASE+5U;
    f->rsp=HTMLK_M4_USER_BASE+4096U;assert(!ACCEPT());f->rsp=HTMLK_M4_USER_STACK-16U;
    assert(!htmlk_m5_timeout_frame_valid(f,top,45U,root+4096U,root));
    assert(!htmlk_m5_timeout_frame_valid(f,top,45U,root,root+4096U));
    assert(!htmlk_m5_timeout_frame_valid(f,top+8U,45U,root,root));
    assert(!htmlk_m5_timeout_frame_valid(f,top,0U,root,root));
    assert(!htmlk_m5_timeout_frame_valid(f,top,4065U,root,root));
    assert(!htmlk_m5_timeout_frame_valid((void *)((uintptr_t)f+8U),top,45U,root,root));
    assert(!htmlk_m5_timeout_frame_valid(0,top,45U,root,root));
    return 0;
}
