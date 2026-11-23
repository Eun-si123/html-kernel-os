/* CPL3 x2APIC timer: 15 GPRs + 5-word hardware CPL3 iret frame.
 * RSP0 per task (NOT IST2). CR3 and TSS.RSP0 updated before iretq.
 * Only -mgeneral-regs-only user payloads supported; no FPU/FS/GS/SMP.
 */
.section .text
.global htmlk_m4_d_timer_entry
.type htmlk_m4_d_timer_entry, @function
htmlk_m4_d_timer_entry:
    pushq %rax
    pushq %rbx
    pushq %rcx
    pushq %rdx
    pushq %rsi
    pushq %rdi
    pushq %rbp
    pushq %r8
    pushq %r9
    pushq %r10
    pushq %r11
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    cld
    movq %rsp, %rdi
    andq $-16, %rsp
    call htmlk_m4_d_timer_handler
    movq %rax, %rsp
    jmp .Ld_restore
.size htmlk_m4_d_timer_entry, .-htmlk_m4_d_timer_entry

.global htmlk_m4_d_enter_first
.type htmlk_m4_d_enter_first, @function
htmlk_m4_d_enter_first:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp, htmlk_m4_saved_main_rsp(%rip)
    movq %rdi, %rsp
    jmp .Ld_restore
.size htmlk_m4_d_enter_first, .-htmlk_m4_d_enter_first

.global htmlk_m4_d_resume_user
.type htmlk_m4_d_resume_user, @function
htmlk_m4_d_resume_user:
    cli
    movq %rdi, %rsp
    jmp .Ld_restore
.size htmlk_m4_d_resume_user, .-htmlk_m4_d_resume_user
.Ld_restore:
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %r11
    popq %r10
    popq %r9
    popq %r8
    popq %rbp
    popq %rdi
    popq %rsi
    popq %rdx
    popq %rcx
    popq %rbx
    popq %rax
    iretq

.global htmlk_m4_d_spurious_entry
.type htmlk_m4_d_spurious_entry, @function
htmlk_m4_d_spurious_entry:
    iretq
.section .note.GNU-stack,"",@progbits
