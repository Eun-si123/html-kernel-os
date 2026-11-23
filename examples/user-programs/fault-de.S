/* Real CPL3 #DE from an integer divide with zero divisor. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movq $42,%rax
    xorq %rdx,%rdx
    xorq %rcx,%rcx
    divq %rcx
    ud2
.section .note.GNU-stack,"",@progbits
