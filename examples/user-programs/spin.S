/* M5-E2 negative user task: NEVER yields, sleeps, syscalls or exits.
 * Only an actual external x2APIC interrupt can return control to kernel. */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    xorq %rax,%rax
.Lrun_forever:
    incq %rax
    rolq $1,%rbx
    jmp .Lrun_forever
.section .note.GNU-stack,"",@progbits
