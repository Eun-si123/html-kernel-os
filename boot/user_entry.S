/* Opt-in true CPL3 entry / int 0x80 interrupt / one-shot return. */
.section .text
#ifdef HTMLK_M5_USER_LOADER
/* M5's single-app supervisor has no FS/GS-relative TLS/per-CPU ABI.
 * Clear selectors AND long-mode bases: loading null alone does not
 * portably clear the hidden base. No SWAPGS or FSGSBASE enable. */
.macro htmlk_m5_clear_segments
    xorl %eax,%eax
    movw %ax,%fs
    movw %ax,%gs
    xorl %edx,%edx
    movl $0xc0000100,%ecx /* IA32_FS_BASE */
    wrmsr
    incl %ecx            /* IA32_GS_BASE */
    wrmsr
.endm
#endif
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
    /* Fresh user flags: architectural bit 1, and IF only for E2.
     * Do not expose supervisor arithmetic flags or inherit DF/TF/IOPL. */
#ifdef HTMLK_M5_USER_TIMEOUT
    pushq $0x202
#else
    pushq $0x2
#endif
    pushq %rdx      /* user CS */
    pushq %rdi      /* user RIP */
#ifdef HTMLK_M5_USER_LOADER
    htmlk_m5_clear_segments
#endif
    /* Entry arguments and caller/callee registers may contain supervisor
     * values. The IRET frame and saved kernel context are complete now.
     * RSP is restored from that frame; clear every other integer register. */
    xorq %rax,%rax
    xorq %rbx,%rbx
    xorq %rcx,%rcx
    xorq %rdx,%rdx
    xorq %rsi,%rsi
    xorq %rdi,%rdi
    xorq %rbp,%rbp
    xorq %r8,%r8
    xorq %r9,%r9
    xorq %r10,%r10
    xorq %r11,%r11
    xorq %r12,%r12
    xorq %r13,%r13
    xorq %r14,%r14
    xorq %r15,%r15
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
#ifdef HTMLK_M5_USER_LOADER
    htmlk_m5_clear_segments
#endif
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
