/* Actual ring3 busy loops: no yields, int80, IO or kernel calls.
 * Timer can observe progress only by reading physical private stack pages.
 * The two images occupy identical user virtual locations under distinct CR3s.
 */
.section .rodata
.global htmlk_m4_d_bad_begin
.global htmlk_m4_d_bad_end
htmlk_m4_d_bad_begin:
    movabsq $0x1122334455667788,%rbx
    movabsq $0x99aabbccddeeff00,%r12
    movabsq $0x0102030405060708,%r10
    movabsq $0x1122334455667788,%r13
.Lm4_d_a_loop:
    cmpq $0x0,-16(%rsp)
    jne .Lm4_d_a_fault
    incq -8(%rsp)
    cmpq %r13,%rbx
    jne .Lm4_d_a_bad_reg
    jmp .Lm4_d_a_loop
.Lm4_d_a_bad_reg:
    ud2
.Lm4_d_a_fault:
#ifdef HTMLK_M4_D_GP_FAULT
    outb %al, $0xe9
#elif defined(HTMLK_M4_D_RO_FAULT)
    movabsq $0x0000400000000000,%rax
    movq $0x55,(%rax)
#else
    movabsq $0xffffffff80001000,%rax
    movq (%rax),%rax
#endif
    ud2
htmlk_m4_d_bad_end:

.global htmlk_m4_d_good_begin
.global htmlk_m4_d_good_end
htmlk_m4_d_good_begin:
    movabsq $0x8877665544332211,%rbx
    movabsq $0x00ffeeddccbbaa99,%r12
    movabsq $0x0807060504030201,%r10
    movabsq $0x8877665544332211,%r13
.Lm4_d_b_loop:
#ifdef HTMLK_M4_D_UNEXPECTED_B_GP
    cmpq $0,-16(%rsp)
    jne .Lm4_d_b_injected_gp
#endif
    incq -8(%rsp)
    cmpq %r13,%rbx
    jne .Lm4_d_b_bad_reg
    jmp .Lm4_d_b_loop
.Lm4_d_b_bad_reg:
    ud2
#ifdef HTMLK_M4_D_UNEXPECTED_B_GP
.Lm4_d_b_injected_gp:
    outb %al,$0xe9  /* unexpected B fault: MUST fail-stop */
#endif
htmlk_m4_d_good_end:
.section .note.GNU-stack,"",@progbits
