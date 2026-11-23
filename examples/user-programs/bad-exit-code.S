/* M5-F4 negative: valid CPL3 handshake/report, then illegal exit 256. */
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
    movq $256, %rdi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
