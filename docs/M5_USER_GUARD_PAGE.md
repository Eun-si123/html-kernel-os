# M5-E3-J — owned user nonpresent guard-page faults with bad RSP

A real pre-fix BIOS QEMU guest at main 5872bf7 exited 45 after a
CPL3 read of the first unmapped page immediately above its one-page
stack, with invalid saved user RSP. Observed IST2 stack marker, #PF
vector 14, CPU error 4 and CR2 at the stack end. The interactive shell
did not survive. This is a known missing E3-H case, not a new OS feature.

Extend the existing exact IST2/error-word/active owner/CR3/RIP/selector/
RFLAGS/bad user stack guard only for nonpresent user data reads (4) and
writes (6) within that one adjacent 4096-byte page. The page table maps
only code and stack in that region. No page is allocated, no user pointer
dereferenced, and no retry of the faulting instruction is attempted.
The existing trusted kernel return and six-frame reclamation path retires
the current program. Existing #PF5/#PF7 policy is unchanged.
Access outside this adjacent page remains fail-stop in the bad-RSP
fallback, as do reserved-bit or instruction-fetch faults, wrong ownership,
legacy non-recovery builds and other invalid frames.

## Reproduction

```sh
python3 -m unittest tests.test_user_fault_policy -v
python3 scripts/test_m5_user_guard_page.py
python3 scripts/test_m5_user_bad_pf_stack.py
```

Host GCC O0/O3 UBSan tests enumerate all 128 low PF error values at the
guard page, check the first/last byte and adjacent exclusions, and verify
owner, valid-stack, already-retired and displaced-frame negatives.
Four successful QEMU boots (one without timer, three with x2APIC) each
retire two faulty apps and resume healthy independently compiled HTMLK
apps. Timed boots also exercise the existing nonyielding app timeout.
Outside-page and legacy fail-stop controls remain. Both real UART and
debugcon are checked for retirement and reclamation markers.

This is a bounded M5-E3 follow-on for the existing one-vCPU trusted
build-time app model, not general arbitrary-code isolation, general
instruction-fetch recovery, stack NX, SMP or hardware support.
CI and physical hardware are separate evidence gates.
