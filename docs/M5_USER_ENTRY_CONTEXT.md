# M5-E3-K — deterministic fresh CPL3 integer register state

On merged main 467d013, a real independently assembled HKEX probe
reports 0 instead of 2026 when it tests the initial integer register
state. The original single-task entry path inherits supervisor register
values, including the arguments used to construct the IRET frame, and
inherits supervisor RFLAGS. This is an unnecessary cross-boundary state
exposure and an unreliable fresh-program ABI.

The entry routine first saves the supervisor callee-saved state and
constructs the existing hardware IRET frame. It then clears all fifteen
non-RSP integer registers before IRET. User RSP and RIP still come from
the validated frame. RFLAGS starts with architectural bit 1 and IF only
for the existing opt-in real x2APIC timeout path. No IOPL, TF, DF or
supervisor arithmetic flags are inherited. The normal syscall/interrupt
resume paths are not fresh-entry paths and do not clear live user state.

## Reproduce

```sh
python3 scripts/test_m5_user_entry_context.py
python3 scripts/test_m4_user.py
python3 scripts/test_m4_isolation.py
python3 scripts/test_m5_process_lifecycle_stress.py
```

The probe captures initial RFLAGS before any arithmetic changes it,
combines all fifteen GPRs, then checks both values in actual CPL3.
No inherited register value is printed or dereferenced. It reports
2026 only if all non-RSP registers are zero and RFLAGS matches the
expected entry mode, otherwise 0. One no-timer and three timed QEMU
boots interleave fresh entry, actual #UD retirement, healthy independent
user runs and (in timed mode) actual x2APIC timeout. Both UART and E9
output, exact page reclamation and a live shell are checked.

This is limited to the common single-task integer entry path.
It does not establish complete CPU state isolation: FPU/SIMD/XSAVE,
FS/GS, debug state, NX, SMP, the separate M4 preemption entry path,
arbitrary-code security, browser compatibility and physical hardware
are separate gates. Kernel return behavior is not redesigned.
