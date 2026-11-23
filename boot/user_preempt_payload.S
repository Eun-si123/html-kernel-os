/* Non-yielding PIC user tasks. They never invoke INT 80, HLT or kernel I/O.
 * Count + sentinel reside on two different physical user stack pages, even
 * though the tasks share the same canonical user virtual addresses. */
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
    movabsq $0x123456789abcdef0, %r13
    cmpq %r13, %rbx
    jne .Ld1_invalid
    movabsq $0x76543210fedcba98, %r13
    cmpq %r13, %r12
    jne .Ld1_invalid
#ifdef HTMLK_M4_D2_FAULT
    cmpq $0, -40(%rsp) /* armed by kernel only after both users progress */
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
    movabsq $0xfedcba9876543210, %r13
    cmpq %r13, %rbx
    jne .Ld1_invalid
    movabsq $0x89abcdef01234567, %r13
    cmpq %r13, %r12
    jne .Ld1_invalid
#ifdef HTMLK_M4_D2_B_FAULT
    cmpq $0, -40(%rsp) /* unexpected survivor fault is fail-stop */
    je .Ld1_b_continue
    outb %al, $0xe9
.Ld1_b_continue:
#endif
    pause
    jmp htmlk_m4_d1_b_loop
htmlk_m4_d1_b_end:
.Ld1_invalid:
    ud2 /* fail-stop if register state is corrupted */
.section .note.GNU-stack,"",@progbits
