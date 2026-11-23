/* Test-only program: privileged port I/O in CPL3 must cause CPU #GP. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movb $0x41, %al
    outb %al, $0xe9
    ud2
.section .note.GNU-stack,"",@progbits
