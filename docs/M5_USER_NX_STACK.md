# M5-E3-N — non-executable private user stack

Merged main 1b95752 permitted execution of a one-byte RET routine written
to the app's own writable stack. Actual QEMU ran that routine and reported
2026. The M5 private stack was writable and executable despite the code
page being read-only.

The M5 loader now checks CPUID extended NX support, enables EFER.NXE if
needed and sets bit 63 only on the private stack leaf PTE. The loaded
code page stays read-only/executable, and the stack stays readable/writable.
The old EFER setting is restored after the common trusted return restores
the supervisor address space. Other M4 paths are unchanged.

On a CPU advertising no NX, the loader retains the old executable-stack
behavior for compatibility; **that configuration has no NX guarantee**.
No new minimum CPU requirement is imposed. Real hardware, browser CPU
compatibility and physical boot remain unverified.

A stack instruction fetch on NX hardware produces actual #PF error 21
(P=1,U=1,I/D=1). Because its saved RIP is in the stack, the ordinary
code-RIP guard must not be weakened to accept it. A separate proof checks
the exact IST2 five-word frame and adjacent error word, selected live
task, six owned frames, current private CR3, trusted supervisor return,
CPL3 selectors and flags, exact error code and CR2 == RIP within the
private stack. It never dereferences the untrusted RIP/RSP, maps the
faulting page, or retries the instruction. Only the offending app retires.

## Verification

```sh
python3 scripts/test_m5_user_nx_stack.py
python3 -m unittest tests.test_user_fault_policy -v
```

Actual QEMU: same stack routine succeeds with CPU model qemu64,-nx;
on NX-capable configurations, one no-timer and three x2APIC boots
interleave two true NX faults, healthy programs and timer termination.
Both UART and debugcon report exact recovery and reclamation counts.
Host GCC UBSan O0/O3 checks all 128 low error codes, stack boundaries,
wrong CR3/selectors, frame offsets, stale owner and unmatched RIP/CR2.
The existing code-RIP/data-fault checks are preserved.
This is a single-app stack protection feature, not general W^X,
full arbitrary-code security, SIMD isolation, or a hardware claim.
