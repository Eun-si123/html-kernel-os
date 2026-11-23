/* M5-F4: valid last-byte INT80 exit code 7, no trailing UD2. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movq $0, %rax
    movq $0x1234, %rdi
    int $0x80
    movq $2, %rax
    movq $2026, %rdi
    int $0x80
    movq $1, %rax
    movq $7, %rdi
    int $0x80
.section .note.GNU-stack,"",@progbits
