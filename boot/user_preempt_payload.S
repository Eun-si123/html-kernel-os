/* Fixed, relocation-free Ring3 payloads. During three x2APIC slices they
 * do not yield or modify ANY GPR. After timer progress, every saved GPR
 * must still match its task-specific initial value or real CPU #UD panics.
 */
.section .rodata
.global htmlk_m4_d_bad_begin
.global htmlk_m4_d_bad_end
htmlk_m4_d_bad_begin:
.Ld_a_loop:
    cmpl $1, -8(%rsp)
    jne .Ld_a_loop
    cmpq $0x100, %r15
    jne .Ld_a_bad_regs
    cmpq $0x101, %r14
    jne .Ld_a_bad_regs
    cmpq $0x102, %r13
    jne .Ld_a_bad_regs
    cmpq $0x103, %r12
    jne .Ld_a_bad_regs
    cmpq $0x104, %r11
    jne .Ld_a_bad_regs
    cmpq $0x105, %r10
    jne .Ld_a_bad_regs
    cmpq $0x106, %r9
    jne .Ld_a_bad_regs
    cmpq $0x107, %r8
    jne .Ld_a_bad_regs
    cmpq $0x108, %rbp
    jne .Ld_a_bad_regs
    cmpq $0x109, %rdi
    jne .Ld_a_bad_regs
    cmpq $0x10a, %rsi
    jne .Ld_a_bad_regs
    cmpq $0x10b, %rdx
    jne .Ld_a_bad_regs
    cmpq $0x10c, %rcx
    jne .Ld_a_bad_regs
    cmpq $0x10d, %rbx
    jne .Ld_a_bad_regs
    cmpq $0x10e, %rax
    jne .Ld_a_bad_regs
    movabsq $0xffffffff80001000, %rax
    movq (%rax), %rax
    ud2
.Ld_a_bad_regs:
    ud2
htmlk_m4_d_bad_end:
.global htmlk_m4_d_good_begin
.global htmlk_m4_d_good_end
htmlk_m4_d_good_begin:
.Ld_b_loop:
    cmpl $1, -8(%rsp)
    jne .Ld_b_loop
    cmpq $0x200, %r15
    jne .Ld_b_bad_regs
    cmpq $0x201, %r14
    jne .Ld_b_bad_regs
    cmpq $0x202, %r13
    jne .Ld_b_bad_regs
    cmpq $0x203, %r12
    jne .Ld_b_bad_regs
    cmpq $0x204, %r11
    jne .Ld_b_bad_regs
    cmpq $0x205, %r10
    jne .Ld_b_bad_regs
    cmpq $0x206, %r9
    jne .Ld_b_bad_regs
    cmpq $0x207, %r8
    jne .Ld_b_bad_regs
    cmpq $0x208, %rbp
    jne .Ld_b_bad_regs
    cmpq $0x209, %rdi
    jne .Ld_b_bad_regs
    cmpq $0x20a, %rsi
    jne .Ld_b_bad_regs
    cmpq $0x20b, %rdx
    jne .Ld_b_bad_regs
    cmpq $0x20c, %rcx
    jne .Ld_b_bad_regs
    cmpq $0x20d, %rbx
    jne .Ld_b_bad_regs
    cmpq $0x20e, %rax
    jne .Ld_b_bad_regs
    movq $0, %rax
    movq $0x1234, %rdi
    int $0x80
#ifdef HTMLK_M4_D_BAD_SYSCALL
    movq $99, %rax
    int $0x80
#endif
#ifdef HTMLK_M4_D_B_FAULT
    outb %al, $0xe9
#endif
    movq $1, %rax
    xorq %rdi, %rdi
    int $0x80
    ud2
.Ld_b_bad_regs:
    ud2
htmlk_m4_d_good_end:
.section .note.GNU-stack,"",@progbits
