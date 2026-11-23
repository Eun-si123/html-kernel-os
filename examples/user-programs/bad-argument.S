/* Test-only: a syntactically valid but disallowed report syscall. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movq $2, %rax
    movq $10000, %rdi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
