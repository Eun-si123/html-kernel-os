/* Opt-in true CPL3 entry / int 0x80 interrupt / one-shot return. */
.section .text
.global htmlk_m4_user_enter
.type htmlk_m4_user_enter, @function
htmlk_m4_user_enter:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp, htmlk_m4_saved_main_rsp(%rip)
    pushq %rcx      /* user SS */
    pushq %rsi      /* user RSP */
    pushfq          /* IF remains 0 in this opt-in no-IRQ proof */
    pushq %rdx      /* user CS */
    pushq %rdi      /* user RIP */
    iretq
.size htmlk_m4_user_enter, .-htmlk_m4_user_enter

.global htmlk_m4_syscall_entry
.type htmlk_m4_syscall_entry, @function
htmlk_m4_syscall_entry:
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
    movq %rsp, %r15
    andq $-16, %rsp
    call htmlk_m4_syscall_dispatch
    movq %r15, %rsp
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
.size htmlk_m4_syscall_entry, .-htmlk_m4_syscall_entry

.global htmlk_m4_user_return
.type htmlk_m4_user_return, @function
htmlk_m4_user_return:
    cli
    movq htmlk_m4_saved_cr3(%rip), %rax
    movq %rax, %cr3
    movq htmlk_m4_saved_main_rsp(%rip), %rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_user_return, .-htmlk_m4_user_return

#ifndef HTMLK_M5_USER_LOADER
/* Position-independent 64-bit user code copied to a private user page.
 * Immediate operands only; NO relocations or kernel pointers. */
.section .rodata
.global htmlk_m4_user_code_begin
.global htmlk_m4_user_code_end
htmlk_m4_user_code_begin:
    movq $0x1234, %rdi
    movq %rdi, -8(%rsp) /* real private ring3 stack store */
    cmpq %rdi, -8(%rsp) /* and actual read back */
    jne .Lm4_user_bad_stack
    movq $0, %rax
    int $0x80
#if defined(HTMLK_M4_USER_BAD_SYSCALL)
    movq $99, %rax
    int $0x80
#elif defined(HTMLK_M4_USER_PRIVILEGED_IO)
    outb %al, $0xe9
#elif defined(HTMLK_M4_USER_READ_KERNEL)
    movabsq $0xffffffff80001000, %rax
    movq (%rax), %rax /* actual CPL3 supervisor access -> #PF */
#elif defined(HTMLK_M4_USER_WRITE_CODE)
    movabsq $0x0000400000000000, %rax
    movq $0x12, (%rax) /* CPL3 write into user RO code -> #PF */
#endif
    movq $1, %rax
    xorq %rdi, %rdi
    int $0x80
    ud2
.Lm4_user_bad_stack:
    ud2
htmlk_m4_user_code_end:
#endif /* not M5 ROMFS external executable mode */
.section .note.GNU-stack,"",@progbits
