/* x86-64 ring-0 timer IRQ: save all GPRs, switch entire saved IRQ stack.
 * Never use this frame for ring-3 tasks or FPU/SIMD contexts. */
.section .text
.global htmlk_m4_x2apic_irq_entry
.type htmlk_m4_x2apic_irq_entry, @function
htmlk_m4_x2apic_irq_entry:
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
    call htmlk_m4_on_timer_irq
    testq %rax, %rax
    jz .Lm4_irq_finished
    movq %rax, %rsp
    jmp .Lm4_restore_irq
.Lm4_irq_finished:
    cli
    movq htmlk_m4_main_stack(%rip), %rsp
    jmp .Lm4_restore_main
.size htmlk_m4_x2apic_irq_entry, .-htmlk_m4_x2apic_irq_entry

.global htmlk_m4_enter_first
.type htmlk_m4_enter_first, @function
htmlk_m4_enter_first:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rsp, htmlk_m4_main_stack(%rip)
    movq %rdi, %rsp
    jmp .Lm4_restore_irq
.Lm4_restore_irq:
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
.Lm4_restore_main:
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    retq
.size htmlk_m4_enter_first, .-htmlk_m4_enter_first
.section .note.GNU-stack,"",@progbits
