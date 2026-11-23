/* Two independently copied, position-independent CPL3 busy loops.
 * Neither yields or makes a progress syscall. A faults; B exits by INT 0x80. */
.section .rodata
.global htmlk_m4_d_a_begin
.global htmlk_m4_d_a_end
htmlk_m4_d_a_begin:
    movabsq $0x1111222233334444, %r12
    movabsq $0xaaaabbbbccccdddd, %r13
    movq $0xa1, %rbx
    movq $0xa2, %rcx
    movq $0xa3, %rdx
    movq $0xa4, %rsi
    movq $0xa5, %rdi
    movq $0xa6, %rbp
    movq $0xa7, %r8
    movq $0xa8, %r9
    movq $0xa9, %r10
    movq $0xaa, %r11
    movq $0xab, %r14
    movq $0xac, %r15
    movabsq $0x123456789abcdef0, %rax
    movq %rax, -24(%rsp)
    movq $0, -8(%rsp)
.Ld_a_loop:
    addq $1, -8(%rsp)
    cmpq $0, -16(%rsp)
    jne .Ld_a_fault
    cmpw $0x4444, %r12w
    jne .Ld_a_bad_reg
    cmpw $0xdddd, %r13w
    jne .Ld_a_bad_reg
    pause
    jmp .Ld_a_loop
.Ld_a_fault:
    movabsq $0xffffffff80001000, %rax
#ifdef HTMLK_M4_D_WRONG_FAULT
    movabsq $0xffffffff80002000, %rax
#endif
    movq (%rax), %rax
.Ld_a_bad_reg:
    ud2
htmlk_m4_d_a_end:
.global htmlk_m4_d_b_begin
.global htmlk_m4_d_b_end
htmlk_m4_d_b_begin:
    movabsq $0x1111222233335555, %r12
    movabsq $0xaaaabbbbccccbeee, %r13
    movq $0xb1, %rbx
    movq $0xb2, %rcx
    movq $0xb3, %rdx
    movq $0xb4, %rsi
    movq $0xb5, %rdi
    movq $0xb6, %rbp
    movq $0xb7, %r8
    movq $0xb8, %r9
    movq $0xb9, %r10
    movq $0xba, %r11
    movq $0xbb, %r14
    movq $0xbc, %r15
    movabsq $0xfedcba9876543210, %rax
    movq %rax, -24(%rsp)
    movq $0, -8(%rsp)
.Ld_b_loop:
    addq $1, -8(%rsp)
#ifdef HTMLK_M4_D_BAD_SURVIVOR
    movabsq $0xffffffff80001000, %rax
    movq (%rax), %rax
#endif
    cmpq $0, -16(%rsp)
    jne .Ld_b_exit
    cmpw $0x5555, %r12w
    jne .Ld_b_bad_reg
    cmpw $0xbeee, %r13w
    jne .Ld_b_bad_reg
    pause
    jmp .Ld_b_loop
.Ld_b_exit:
    movq $1, %rax
    xorq %rdi, %rdi
    int $0x80
.Ld_b_bad_reg:
    ud2
htmlk_m4_d_b_end:
.section .note.GNU-stack,"",@progbits
