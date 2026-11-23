/* Fixed trusted CPL3 test payload. 15 GPRs are independently checked
 * by the actual CPU on every nonyielding loop iteration after x2APIC IRQ.
 * Constants are RIP-relative in copied RO user code, never kernel pointers.
 */
.section .rodata
.global htmlk_m4_d1_a_begin
.global htmlk_m4_d1_a_end
.global htmlk_m4_d1_a_loop
htmlk_m4_d1_a_begin:
    movq $0xa11a, -8(%rsp)
    movabsq $0x123456789abcdef0, %rbx
    movabsq $0x76543210fedcba98, %r12
htmlk_m4_d1_a_loop:
    incq -16(%rsp)
    cmpq $0x100, %r15
    jne .Ld1_a_invalid
    cmpq $0x101, %r14
    jne .Ld1_a_invalid
    cmpq $0x102, %r13
    jne .Ld1_a_invalid
    cmpq .La_r12(%rip), %r12
    jne .Ld1_a_invalid
    cmpq $0x104, %r11
    jne .Ld1_a_invalid
    cmpq $0x105, %r10
    jne .Ld1_a_invalid
    cmpq $0x106, %r9
    jne .Ld1_a_invalid
    cmpq $0x107, %r8
    jne .Ld1_a_invalid
    cmpq $0x108, %rbp
    jne .Ld1_a_invalid
    cmpq $0x109, %rdi
    jne .Ld1_a_invalid
    cmpq $0x10a, %rsi
    jne .Ld1_a_invalid
    cmpq $0x10b, %rdx
    jne .Ld1_a_invalid
    cmpq $0x10c, %rcx
    jne .Ld1_a_invalid
    cmpq .La_rbx(%rip), %rbx
    jne .Ld1_a_invalid
    cmpq $0x10e, %rax
    jne .Ld1_a_invalid
#ifdef HTMLK_M4_D2_FAULT
    cmpq $0, -40(%rsp) /* armed only when A/B have progressed */
    je .Ld1_a_continue
#if defined(HTMLK_M4_D2_A_GP)
.global htmlk_m4_d1_a_fault
htmlk_m4_d1_a_fault:
    outb %al, $0xe9 /* actual ring3 privileged port IO -> #GP(0) */
#elif defined(HTMLK_M4_D2_A_RO)
    movabsq $0x0000400000000000, %rax
.global htmlk_m4_d1_a_fault
htmlk_m4_d1_a_fault:
    movq $0x55, (%rax) /* actual ring3 RO-code write -> #PF(7) */
#else
    movabsq $0xffffffff80001000, %rax
.global htmlk_m4_d1_a_fault
htmlk_m4_d1_a_fault:
    movq (%rax), %rax /* real ring3 supervisor read -> #PF(5) */
#endif
.Ld1_a_continue:
#endif
    pause
    jmp htmlk_m4_d1_a_loop
.Ld1_a_invalid:
    ud2
.La_rbx:
    .quad 0x123456789abcdef0
.La_r12:
    .quad 0x76543210fedcba98
htmlk_m4_d1_a_end:

.global htmlk_m4_d1_b_begin
.global htmlk_m4_d1_b_end
.global htmlk_m4_d1_b_loop
htmlk_m4_d1_b_begin:
    movq $0xb22b, -8(%rsp)
    movabsq $0xfedcba9876543210, %rbx
    movabsq $0x89abcdef01234567, %r12
htmlk_m4_d1_b_loop:
    incq -16(%rsp)
    cmpq $0x200, %r15
    jne .Ld1_b_invalid
    cmpq $0x201, %r14
    jne .Ld1_b_invalid
    cmpq $0x202, %r13
    jne .Ld1_b_invalid
    cmpq .Lb_r12(%rip), %r12
    jne .Ld1_b_invalid
    cmpq $0x204, %r11
    jne .Ld1_b_invalid
    cmpq $0x205, %r10
    jne .Ld1_b_invalid
    cmpq $0x206, %r9
    jne .Ld1_b_invalid
    cmpq $0x207, %r8
    jne .Ld1_b_invalid
    cmpq $0x208, %rbp
    jne .Ld1_b_invalid
    cmpq $0x209, %rdi
    jne .Ld1_b_invalid
    cmpq $0x20a, %rsi
    jne .Ld1_b_invalid
    cmpq $0x20b, %rdx
    jne .Ld1_b_invalid
    cmpq $0x20c, %rcx
    jne .Ld1_b_invalid
    cmpq .Lb_rbx(%rip), %rbx
    jne .Ld1_b_invalid
    cmpq $0x20e, %rax
    jne .Ld1_b_invalid
#ifdef HTMLK_M4_D2_B_FAULT
    cmpq $0, -40(%rsp)
    je .Ld1_b_continue
    outb %al, $0xe9 /* unexpected survivor #GP is fail-stop */
.Ld1_b_continue:
#endif
    pause
    jmp htmlk_m4_d1_b_loop
.Ld1_b_invalid:
    ud2
.Lb_rbx:
    .quad 0xfedcba9876543210
.Lb_r12:
    .quad 0x89abcdef01234567
htmlk_m4_d1_b_end:

.section .note.GNU-stack,"",@progbits
