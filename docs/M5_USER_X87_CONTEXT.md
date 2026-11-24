# M5-E3-L — fresh legacy x87 context at M5 app entry

On main 467d013, two independent real CPL3 HKEX programs ran in BIOS
QEMU. The first executed FLD1 and exited; the second observed nonzero
x87 TOP and reported failure (0). This is actual cross-program legacy
floating-point state retention. A separate SSE probe generated #UD in
the baseline QEMU configuration: SSE is not enabled by this change.

In the existing single-active-app M5 loader, when CR0.EM and CR0.TS are
both clear, save the supervisor's 108-byte legacy x87 environment and
register state using FNSAVE before entering CPL3. Explicitly overwrite
all eight physical x87 registers with zero before FNINIT marks them
empty. On the common trusted return path after exit, fault or timeout,
FNCLEX discards pending user exceptions before FRSTOR reloads the saved
legacy state. All current kernel C/interrupt code uses
-mgeneral-regs-only. No kernel FP arithmetic, CR0/CR4 feature enabling,
or new language floating-point type is introduced.

The legacy FNSAVE format is not full 64-bit extended CPU context
(in particular it does not preserve full-width FIP/FDP). This does not
claim a general kernel FPU ABI. If EM or TS is set, the loader does not
execute x87 management instructions; unsupported-device fault handling
is unchanged. SSE/AVX, MXCSR, XSAVE, FS/GS, #MF/#NM recovery,
concurrent/preemptively switched app contexts, arbitrary-code security,
browser and physical hardware remain separate gates.

## Reproduction

```sh
python3 scripts/test_m5_user_x87_context.py
```

Actual CPL3 independently dirties the x87 control word and eight
physical registers, then exits, faults with UD2, or spins until the
existing hardware timer expires. Another program inspects its own
108-byte FNSAVE image, checking default control/status/tag fields and
all 80 register-data bytes. A pending-exception-producing user sequence
also exercises the common return. The test never prints register
contents. It verifies the exact success/error/reclamation counts in
real UART and E9 and clean shell exit on one no-timer and three timed
QEMU boots. No-timer defaults and reserved builder ROMFS paths remain
unchanged. Exact CI and physical hardware are separate evidence gates.
