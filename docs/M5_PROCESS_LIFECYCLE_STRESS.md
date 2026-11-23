# M5-E3 — interleaved real Ring3 process lifecycle regression

**Scope:** repeatable integration testing on one QEMU q35 x86-64 vCPU. This is **not** a general-purpose security/auditing certification of arbitrary HKEX programs. Local QEMU test PASS; exact PR-head GitHub CI and merge require separate confirmation.

## Test

```sh
python3 scripts/test_m5_process_lifecycle_stress.py
```

The test uses **the same actual native kernel**, pinned Limine boot flow, real emulated 16550 COM1 UART RX and E9 debugcon, and the real single-vCPU x2APIC timer used by merged M5-E2. Two additional, independently assembled user programs are embedded via `--romfs-root` without altering the source ROMFS directory: an unknown `INT 0x80` ID and a recognized syscall with an out-of-range argument. These are **executed in CPU CPL3**, not software mocks, and the existing M5-E1 process-only retirement takes effect.

In each of three separate complete BIOS QEMU boots, the host sends 19 actual UART commands. Each boot interleaves:

- Seven successful executions of the separately assembled `/apps/hello.hke`, reporting `M5_C_USER_VALUE=2026` and a fresh six-frame reclaim each time.
- Two runs of truly nonyielding `/apps/spin.hke`: an actual x2APIC timer interrupts Ring3 and terminates only that program on its fourth real IRQ. Kernel-owned frames are reclaimed and the prompt resumes.
- Four real CPL3 CPU faults: privileged port I/O (#GP), supervisor access (#PF 5), write to read-only user executable page (#PF 7), and UD2 (#UD). IST2 and privilege checks remain active; every offending process retires without kernel reset.
- Two protocol-invalid user syscalls, separately encoded in the HKEX payloads, each with its own six-frame reclaim and `M5_ERR_USER_SYSCALL`. These must **not** be falsely treated as CPU exceptions.
- `help`, `cat`, a missing file path, a clean `exit` and the *actual HTML-derived native kernel output*.

The test checks event ordering, exactly seven process-success traces, two timeout traces, four CPU-fault reclamations, two invalid-syscall reclamations, successful serial output, zero stale fatal markers and the correct QEMU debug-exit status. This is a stronger **cross-feature regression** than running M5-C1/D1/E1/E2 in isolation. No harness-internal timer or prerecorded guest log can pass these QEMU assertions.

## Limits and remaining E3 work

This validates a **known, trusted, build-time** set of fixed-size HKEX programs only. FNV is an accidental-corruption check, not a code signature. One concurrent process runs at a time. The IRQ budget is not wall-clock calibrated. Dynamic task concurrency, FPU/XSAVE, FS/GS, nested interrupts, SMP, robust code provenance, syscall pointer copyin/out, general process authentication, device/disk safety, UEFI and **physical PC boot** remain outside this evidence. Continue E3 security review and failure-injection negative controls before considering the full M5 reliability gate closed. [Issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
