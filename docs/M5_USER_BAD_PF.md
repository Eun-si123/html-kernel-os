# M5-E3-H — true Ring3 page faults on IST2 after poisoning the user RSP

**Status: exact PR-head GitHub CI/Gitleaks and merge must be verified independently.** Local real BIOS QEMU with/without genuine x2APIC and GCC UBSan policy tests PASS. This is a **narrow known-task opt-in** fault recovery, not general-purpose process or arbitrary-ELF security.

## Independently reproduced kernel-liveness failure

Before the change on merged `dfd9cb3`, a separately assembled, valid bounded Ring3 HKEX app executed `xorq %rsp,%rsp` followed by a genuine read from high privileged `0xffffffff80001000`. Actual QEMU then delivered #PF vector 14 on **TSS.IST2**, with CPU error code `5`, CR2=`0xffffffff80001000` and the real diagnostic `M3_IST_PF_STACK_OK`. Because the saved **user** RSP was poisoned, the existing strict M5-E1 recovery refused, and the **entire interactive kernel exited** QEMU with code **45** (`M3_EXCEPTION V=0E`), not a process-only retirement. M5-E3-G covered #GP on the distinct RSP0 stack, not #PF IST2.

## Explicit CPU frame and ownership boundary

For #PF, the CPU pushes **six** qwords: its 8-byte error word and five-qword privileged IRET frame (RIP/CS/RFLAGS/RSP/SS) on *the actual hardware IST2 stack*, rather than TSS.RSP0 used by the earlier #GP code. In GCC's x86-64 interrupt-handler ABI, the `struct interrupt_frame *f` points at the saved RIP after the error word. This proof explicitly requires the actual exception frame address to be **trusted TSS.IST2_top − 40**, the CPU error word to be **trusted TSS.IST2_top − 48**, and `error_word_address == f−8`. It checks the already validated current execution of the handler is inside the actual PF IST stack, **saved CPU CS has CPL3**, and a current process owner is live, with owned private CR3, six pages and no prior retirement. It validates the exact user executable RIP bounds, selector 0x2b/0x33, expected RFLAGS/IF, safe saved kernel CR3 and stack, high-canonical aligned IST2 top, and the poisoned user RSP being **outside** its permitted user stack interval. No user-controlled pointer, saved RSP or CR2 is dereferenced.

The new second-chance policy admits only *present-page, user-origin* CPU #PF with error code **5** (attempted user read of a canonical high supervisor address in CR2) or **7** (attempted write to the known private RX user code page). All other #PF error codes, including **4** (user nonpresent page), remain **unhandled in the second-chance bad-RSP path**. Valid user-stack #PF still uses the original strict M5-E1 handler. The separate M4-D2/other fault handlers and kernel-origin CPL0 fail-stop behavior are unchanged. When all checks pass, only the known current user app is marked faulted; existing no-return kernel CR3/RSP restoration and six-frame reclamation return to the same live COM1 console with `M5_ERR_USER_FAULT`. Distinct evidence markers: `M5_E3_USER_PF5_BAD_RSP_RETIRED` / `M5_E3_USER_PF7_BAD_RSP_RETIRED`.

## Genuine acceptance and negatives

```sh
python3 -m unittest tests.test_user_fault_policy -v
python3 scripts/test_m5_user_bad_pf_stack.py
```

- Before fix: actual #PF5, `M3_IST_PF_STACK_OK`, `V=0E`, `ERROR=5`, `CR2=FFFFFFFF80001000`, QEMU exit **45** with no surviving prompt.
- After fix, **without timer**, true CPU #PF5 and #PF7 each retire one poisoned-stack Ring3 app, reclaim six frames and permit an independent native HTML Ring3 user rerun.
- With actual one-vCPU QEMU x2APIC: **three complete BIOS guest boots**, each boot five independently assembled poisoned-RSP user images (four real #PF5 RSP variants; one real #PF7), **six healthy HTML user program reruns**, plus real nonyielding app expiration on the actual x2APIC interrupt. All **15 true #PF task retirements**, **18 healthy user reruns**, **three timer expirations**, guest final exits and separately captured actual UART/E9 output PASS.
- Negative real CPU: an invalid user non-present #PF error4 with bad RSP still kills the kernel (QEMU exit45). Legacy standalone M5-C1 still exits 45 on actual CPL3 #PF with bad RSP. No success from relaxing strict legacy policies.
- Host GCC UBSan `-O0/-O3` denies forged `IST2_top`, displaced CPU RIP frame or error-word address, wrong CPL/CS/SS, wrong CR3/owner, stale already retired task, valid stack, wrong code RIP, invalid RFLAGS, noncanonical or wrong CR2, and all CPU PF error codes beyond 5/7. Existing #UD/#DE/#GP/IRQ user recovery tests must also be rerun.

## Limits and next gate

This does not establish all #PF vectors/CR2 contexts, nested exception safety, FS/GS/FPU/SMP, arbitrary untrusted execution, full ELF, UEFI, physical hardware or cryptographic code authenticity. Timer-enabled test uses QEMU +x2apic, **not** browser v86; the published M5 Web-Live ISO intentionally has no such deadline. The project M5-E3 fault model still requires scope-specific negative tests and M6 physical hardware is NOT RUN. Reference [M5 issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75) and [CPU bad-stack tracker #91](https://github.com/Eun-si123/html-kernel-os/issues/91).
