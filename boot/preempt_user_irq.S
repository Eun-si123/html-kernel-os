/* M4-D x86-64: full register frame + ring3 CS/SS/RSP in each kernel stack.
 * The CPU switches stacks through the task's TSS.RSP0 before IRQ entry.
 * Never assume this code handles CPL0->CPL0 frames or FPU/FS/GS contexts.
 */
.section .text
.global htmlk_m4_d_timer_entry
.type htmlk_m4_d_timer_entry,@function
htmlk_m4_d_timer_entry:
    pushq %rax
    pushq %rbx
    pushq %rcx
    pushq %rdx
    pushq %rsi
    pushq %rdi
    pushq %rbp
    pushq %r8
    pushq %r9
    pushq %r10
    pushq %r11
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    cld
    movq %rsp, %rdi
    andq $-16,%rsp
    call htmlk_m4_d_on_timer
    testq %rax, %rax
    jz .Lm4_d_finished
    movq %rax, %rsp
    jmp .Lm4_d_restore
.Lm4_d_finished:
    cli
    movq htmlk_m4_d_main_rsp(%rip),%rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_d_timer_entry,.-htmlk_m4_d_timer_entry

.global htmlk_m4_d_enter
.type htmlk_m4_d_enter,@function
htmlk_m4_d_enter:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp,htmlk_m4_d_main_rsp(%rip)
    movq %rdi,%rsp
    jmp .Lm4_d_restore
.size htmlk_m4_d_enter,.-htmlk_m4_d_enter

.global htmlk_m4_d_resume
.type htmlk_m4_d_resume,@function
htmlk_m4_d_resume:
    cli
    movq %rdi,%rsp
.Lm4_d_restore:
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %r11
    popq %r10
    popq %r9
    popq %r8
    popq %rbp
    popq %rdi
    popq %rsi
    popq %rdx
    popq %rcx
    popq %rbx
    popq %rax
    iretq
.size htmlk_m4_d_resume,.-htmlk_m4_d_resume

.global htmlk_m4_d_spurious_entry
.type htmlk_m4_d_spurious_entry,@function
htmlk_m4_d_spurious_entry:
    iretq  /* APIC spurious IRQ requires no EOI */
.size htmlk_m4_d_spurious_entry,.-htmlk_m4_d_spurious_entry
.section .note.GNU-stack,"",@progbits
