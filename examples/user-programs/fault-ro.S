/* M5-E1 actual Ring3 write to user RO code page -> CPU #PF error 7. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movabsq $0x0000400000000000, %rax
    movq $0x12, (%rax)
    ud2
.section .note.GNU-stack,"",@progbits
