/* CPL3 timer IRQ: CPU switches via per-task TSS.RSP0 first, then save GPRs.
 * All contexts contain SS/RSP; never reuse the CPL0-only scheduler's frame. */
.section .text
.global htmlk_m4_d1_irq_entry
.type htmlk_m4_d1_irq_entry, @function
htmlk_m4_d1_irq_entry:
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
    call htmlk_m4_d1_on_irq
    testq %rax, %rax
    jz .Ld1_done
    movq %rax, %rsp
    jmp .Ld1_iret
.Ld1_done:
    cli
    movq htmlk_m4_d1_main_rsp(%rip), %rsp
    jmp .Ld1_main_restore
.size htmlk_m4_d1_irq_entry, .-htmlk_m4_d1_irq_entry

.global htmlk_m4_d1_start
.type htmlk_m4_d1_start, @function
htmlk_m4_d1_start:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp, htmlk_m4_d1_main_rsp(%rip)
    movq %rdi, %rsp
.Ld1_iret:
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
.Ld1_main_restore:
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_d1_start, .-htmlk_m4_d1_start

/* GCC #PF handler runs on IST2, not on faulted user's kernel stack.
 * Abandon the CPU error-code frame and restore preempted survivor context. */
.global htmlk_m4_d1_switch_from_fault
.type htmlk_m4_d1_switch_from_fault, @function
htmlk_m4_d1_switch_from_fault:
    cli
    movq %rdi, %rsp
    jmp .Ld1_iret
.size htmlk_m4_d1_switch_from_fault, .-htmlk_m4_d1_switch_from_fault

.global htmlk_m4_d1_spurious
.type htmlk_m4_d1_spurious, @function
htmlk_m4_d1_spurious:
    iretq /* architectural APIC spurious vector: NO EOI */
.size htmlk_m4_d1_spurious, .-htmlk_m4_d1_spurious
.section .note.GNU-stack,"",@progbits
