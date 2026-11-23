/* Test-only program: a genuine CPL3 unsupported syscall must fail-stop. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movl $99, %eax
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
