/* M5-E1 actual guest user-mode invalid opcode CPU exception. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    ud2
.section .note.GNU-stack,"",@progbits
