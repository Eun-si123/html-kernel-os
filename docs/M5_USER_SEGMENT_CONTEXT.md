# M5-E3-M — fresh FS/GS segment context for the single-app loader

On merged main b27a250, real CPL3 HKEX programs loaded selector 0x33
into FS and GS, then exited normally or via UD2. A separate program
checking its initial selectors reported 0 instead of 2026. The first
run before the dirty app passed; subsequent runs inherited the selectors.

For the M5 loader only, the existing fresh-entry assembly clears both
selectors and explicitly zeroes IA32_FS_BASE and IA32_GS_BASE using
WRMSR. Clearing a selector alone is not a portable hidden-base reset.
The same reset runs at the common terminal return, before resuming the
supervisor's saved stack. No ordinary returning syscall changes the
live app's FS/GS state. GPR initialization follows the entry reset, so
MSR instruction operands do not leak into the app ABI.

This is a deliberately zero-FS/GS supervisor ABI, **not** preservation of
arbitrary supervisor TLS state. The current kernel has no FS/GS-relative
TLS or per-CPU ABI, is built without stack protector, and uses no SWAPGS.
The current single-task M5 exception and IRQ handlers must continue
not to depend on user-controlled FS/GS. A future TLS/per-CPU design must
replace this convention with a real entry/exit context protocol.
IA32_KERNEL_GS_BASE, FSGSBASE enable, separate preemptive scheduling,
extended CPU state, arbitrary-code security and hardware remain open.

## Reproduce

```sh
python3 scripts/test_m5_user_segment_context.py
```

Actual QEMU checks initial null selectors and FS/GS-relative reads of
a known private-stack value. Separate programs dirty the selectors
then exit, raise UD2 or run until real x2APIC timeout. A fresh app runs
after each, and both UART/E9 must show exact reports, reclaimed frames
and clean shell exit. One no-timer and three timed boots pass locally.
This checks selectors and effective zero-base accesses, not the full
FSGSBASE instruction path. Exact-head CI, public browser and physical
PC are separate evidence gates.
