/* SysV AMD64 kernel-to-kernel stack context switch. No CR3, FPU or CPL switch. */
.section .text
.global htmlk_m4_context_switch
.type htmlk_m4_context_switch, @function
htmlk_m4_context_switch:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp, (%rdi)
    movq %rsi, %rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_context_switch, .-htmlk_m4_context_switch
.section .note.GNU-stack,"",@progbits
