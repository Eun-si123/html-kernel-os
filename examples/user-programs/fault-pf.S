/* M5-E1 true user-mode supervisor-only memory access -> CPU #PF. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movabsq $0xffffffff80001000, %rax
    movq (%rax), %rax
    ud2
.section .note.GNU-stack,"",@progbits
