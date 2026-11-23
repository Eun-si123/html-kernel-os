/* Actual INT3 single-byte Ring3 breakpoint trap (#BP, vector 3). */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    int3
    ud2
.section .note.GNU-stack,"",@progbits
