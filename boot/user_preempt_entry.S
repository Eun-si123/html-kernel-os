/* M4-D: reuse M4-B2 general register IRQ frame for final CPL3 syscall.
 * The only permitted user syscall is the terminating survivor exit. */
.section .text
.global htmlk_m4_d_syscall_entry
.type htmlk_m4_d_syscall_entry, @function
htmlk_m4_d_syscall_entry:
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
    andq $-16, %rsp
    call htmlk_m4_d_user_syscall
    ud2
.size htmlk_m4_d_syscall_entry, .-htmlk_m4_d_syscall_entry
.global htmlk_m4_d_return_main
.type htmlk_m4_d_return_main, @function
htmlk_m4_d_return_main:
    cli
    movq htmlk_m4_main_stack(%rip), %rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_d_return_main, .-htmlk_m4_d_return_main
.section .note.GNU-stack,"",@progbits
