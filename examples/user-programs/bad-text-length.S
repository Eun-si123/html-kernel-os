/* M5-F2: user code-page pointer with overflowing untrusted length. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    mov $0x1234, %edi
    xor %eax, %eax
    int $0x80
    mov $3, %eax
    movabsq $0x400000000000, %rdi
    movabsq $0xffffffffffffffff, %rsi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
