/* HKEX code offset zero: only position-relative internal function calls. */
.section .text.entry,"ax"
.global htmlk_user_program_start
.type htmlk_user_program_start,@function
htmlk_user_program_start:
    call htmlk_user_main
    ud2
.size htmlk_user_program_start,.-htmlk_user_program_start
.section .note.GNU-stack,"",@progbits
