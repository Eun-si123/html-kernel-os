/* M5-F2: real CPL3 syscall passes an unmapped supervisor pointer, never dereferenced. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    mov $0x1234, %edi
    xor %eax, %eax
    int $0x80
    mov $3, %eax
    movabsq $0xffffffff80001000, %rdi
    mov $6, %esi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
