/* M5-F2: well-mapped pointer to an ESC sequence, must not alter prompt. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    mov $0x1234, %edi
    xor %eax, %eax
    int $0x80
    mov $3, %eax
    leaq .Ltext(%rip), %rdi
    mov $3, %esi
    int $0x80
    ud2
.Ltext:
    .byte 0x1b,0x5b,0x0a
.section .note.GNU-stack,"",@progbits
