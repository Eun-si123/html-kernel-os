/* M5-F5 denial oracle: legacy M5-C1 must still reject >9999 report. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movq $0, %rax
    movq $0x1234, %rdi
    int $0x80
    movq $2, %rax
    movq $10000, %rdi
    int $0x80
    movq $1, %rax
    xorq %rdi, %rdi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
