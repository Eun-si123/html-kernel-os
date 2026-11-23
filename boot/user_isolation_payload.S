/* Two independent fixed ring3 test images, copied into distinct user pages.
 * No ELF loader, no user pointer with kernel provenance, no voluntary yield. */
.section .rodata
.global htmlk_m4_iso_bad_begin
.global htmlk_m4_iso_bad_end
htmlk_m4_iso_bad_begin:
    movq $0x1111, -8(%rsp)
    movq $2, %rax
    movq $0xa55a, %rdi
    int $0x80
#if defined(HTMLK_M4_ISO_GP)
    outb %al, $0xe9           /* real user -> ring0 #GP(0) */
#elif defined(HTMLK_M4_ISO_RO)
    movabsq $0x0000400000000000, %rax
    movq $0x12, (%rax)       /* real user protection #PF(7) */
#else
    movabsq $0xffffffff80001000, %rax
    movq (%rax), %rax        /* real user kernel access #PF(5) */
#endif
    ud2
htmlk_m4_iso_bad_end:
.global htmlk_m4_iso_good_begin
.global htmlk_m4_iso_good_end
htmlk_m4_iso_good_begin:
    cmpq $0, -8(%rsp)       /* identical virtual stack, different physical page */
    jne .Lbad_good_stack
    movq $0x2222, -8(%rsp)
    movq $0, %rax
    movq $0x1234, %rdi
    int $0x80
#ifdef HTMLK_M4_ISO_SURVIVOR_FAULT
    outb %al, $0xe9 /* B fault must NEVER use A-only recovery path */
#endif
    movq $1, %rax
    xorq %rdi, %rdi
    int $0x80
.Lbad_good_stack:
    ud2
htmlk_m4_iso_good_end:
.section .note.GNU-stack,"",@progbits
