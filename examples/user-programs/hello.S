/* M5-C1 standalone Ring3 program, assembled as a genuine flat binary.
 * No kernel symbols or relocations; explicit INT 0x80 register-only ABI:
 *  syscall 0 (rdi=0x1234): proof of private CPL3 stack
 *  syscall 2 (rdi=2026): report a source-derived numeric value
 *  syscall 1 (rdi=0): terminate and reclaim the task's frames.
 */
.section .text
.global htmlk_user_program_start
htmlk_user_program_start:
    movq $0x1234, %rdi
    movq %rdi, -8(%rsp)
    cmpq %rdi, -8(%rsp)
    jne .Lbad
    xorl %eax, %eax
    int $0x80
    movl $2026, %edi
    movl $2, %eax
    int $0x80
    movl $1, %eax
    xorl %edi, %edi
    int $0x80
.Lbad:
    ud2
.section .note.GNU-stack,"",@progbits
