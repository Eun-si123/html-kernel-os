#include "preempt_user.h"
#include "user_pages.h"
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>

static struct htmlk_m4_d_frame frame(unsigned task) {
    struct htmlk_m4_d_frame f = {0};
    f.rip = HTMLK_M4_USER_BASE;
    f.rsp = HTMLK_M4_USER_STACK - 16U;
    f.cs = 0x2bU; f.ss = 0x33U;
    f.rflags = 0x202U;
    f.rbx = task == 0U?HTMLK_M4_D_A_RBX:HTMLK_M4_D_B_RBX;
    f.r12 = task == 0U?HTMLK_M4_D_A_R12:HTMLK_M4_D_B_R12;
    f.r10 = task == 0U?HTMLK_M4_D_A_R10:HTMLK_M4_D_B_R10;
    f.r13 = f.rbx;
    return f;
}
int main(void) {
    assert(sizeof(struct htmlk_m4_d_frame)==160U);
    assert(offsetof(struct htmlk_m4_d_frame,r15)==0U);
    assert(offsetof(struct htmlk_m4_d_frame,r13)==16U);
    assert(offsetof(struct htmlk_m4_d_frame,r12)==24U);
    assert(offsetof(struct htmlk_m4_d_frame,r10)==40U);
    assert(offsetof(struct htmlk_m4_d_frame,rbx)==104U);
    assert(offsetof(struct htmlk_m4_d_frame,rax)==112U);
    assert(offsetof(struct htmlk_m4_d_frame,rip)==120U);
    assert(offsetof(struct htmlk_m4_d_frame,cs)==128U);
    assert(offsetof(struct htmlk_m4_d_frame,rflags)==136U);
    assert(offsetof(struct htmlk_m4_d_frame,rsp)==144U);
    assert(offsetof(struct htmlk_m4_d_frame,ss)==152U);
    struct htmlk_m4_d_frame a=frame(0),b=frame(1);
    assert(htmlk_m4_d_arch_frame_valid(&a,0,128));
    assert(htmlk_m4_d_arch_frame_valid(&b,1,128));
    assert(!htmlk_m4_d_arch_frame_valid(0,0,128));
    assert(!htmlk_m4_d_arch_frame_valid(&a,2,128));
    assert(!htmlk_m4_d_arch_frame_valid(&a,0,0));
    assert(!htmlk_m4_d_arch_frame_valid(&a,0,4097));
    assert(!htmlk_m4_d_arch_frame_valid(&a,1,128));
    assert(!htmlk_m4_d_arch_frame_valid(&b,0,128));
    a.cs=8; assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.cs=0x2b;
    a.ss=0x10; assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.ss=0x33;
    a.rip=HTMLK_M4_USER_BASE-1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rip=HTMLK_M4_USER_BASE+128;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rip=HTMLK_M4_USER_BASE;
    a.rsp=HTMLK_M4_USER_STACK-4096;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rsp=HTMLK_M4_USER_STACK+1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rsp=HTMLK_M4_USER_STACK-16;
    a.rflags=2;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rflags=0x3202;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));
    a.rflags=0x202;
    a.rbx^=1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.rbx^=1;
    a.r12^=1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.r12^=1;
    a.r10^=1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.r10^=1;
    a.r13^=1;assert(!htmlk_m4_d_arch_frame_valid(&a,0,128));a.r13^=1;
    assert(htmlk_m4_d_arch_frame_valid(&a,0,128));
    puts("M4-D CPL3 SAVED IRQ FRAME AND NEGATIVE STATES PASS");
}
