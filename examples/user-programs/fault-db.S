/* ICEBP/INT1 single-byte Ring3 debug exception (#DB, vector 1). */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    .byte 0xf1
    ud2
.section .note.GNU-stack,"",@progbits
