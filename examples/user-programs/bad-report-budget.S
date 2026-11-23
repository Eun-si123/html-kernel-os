/* Real Ring3: 9th numeric syscall exhausts 8-report per-task budget. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movl $0x1234,%edi
    xorl %eax,%eax
    int $0x80
    movl $2,%eax
    movl $777,%edi
    .rept 9
        int $0x80
    .endr
    movl $1,%eax
    xorl %edi,%edi
    int $0x80
    ud2
.section .note.GNU-stack,"",@progbits
