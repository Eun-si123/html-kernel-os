# M3 — opt-in x86-64 CPU exception IDT (fail-stop prototype)

**Scope:** hardware CPU exception handling in the actual native kernel. This is an **opt-in partial M3 implementation**, not recovered faults, user/kernel isolation, interrupt-driven input, multitasking, or completed M3.

## Architecture

- The boot entry installs a new 256-descriptor **x86-64 IDT** before running the HTML-derived kernel when explicitly requested with `--exception-idt`.
- Vectors 0..31 have actual CPU interrupt-gate entries, using the current kernel code segment and GCC's `__attribute__((interrupt))` ABI with `-mgeneral-regs-only`, `-mno-red-zone` and a pinned baseline x86-64 ISA. Architecturally defined error-code vectors 8, 10–14, 17, 21, 29, 30 use handlers with an error-code argument; the others use the no-code signature.
- The IDT is permanent static kernel memory; descriptor construction is a separate C11 function independently tested against the 16-byte x86-64 layout, selector, canonical handler addresses, reserved fields and error inputs.
- All handlers are **fail-stop**: they turn interrupts off, write the vector number, saved RIP and CPU error code to COM1/debugcon, optionally report CR2 for #PF, and halt. QEMU test images additionally issue a non-success exit with status **45**. They do not skip the faulting instruction or pretend to recover.
- External IRQ delivery is not supported. IF remains disabled; no PIC/APIC, IRQ acknowledgement, interrupt-stack-table (IST), TSS, SMP or user-to-kernel ring transition is configured. **Double faults or faults involving a broken stack may still triple-fault.** Physical PC boot is not validated. No application code can directly manipulate the IDT.

## Reproduce

```sh
python3 scripts/test_exception_idt.py
python3 scripts/build_boot.py --exception-idt --out build/html-kernel-m3-exceptions.iso
```

The QEMU end-to-end script creates two independently bootable sources (baseline and a modified HTML input), confirms the `M3_IDT_READY` prefix, and proves source-dependent native execution still works. Four fault images then **execute actual faulting CPU instructions** and verify the precise vector, 16-digit saved RIP, error-code field and non-success status, rejecting any accidental continuation to HTML source:

| Test flag | CPU exception | Trigger | Expected |
| --- | --- | --- | --- |
| `--fault-test divide` | `#DE` vector 0 | `div` with zero divisor | controlled halt / 45 |
| `--fault-test ud` | `#UD` vector 6 | `ud2` | controlled halt / 45 |
| `--fault-test general` | `#GP` vector 13 | noncanonical linear address | controlled halt / 45 |
| `--fault-test page` | `#PF` vector 14 | read unmapped `0x40000000` | CR2 recorded, halt / 45 |

The test also boots a **combined IDT + existing Limine physical page probe + real Limine RGB framebuffer** image, checking that previous working M3 features remain composable. Other CPU vectors are installed but **not independently exercised** in QEMU.

Host-side gate-construction tests run at GCC `-O0` and `-O3` with UBSan, checking accepted and rejected canonical addresses. The actual CPU faults are independently checked under BIOS QEMU; no claim is made about real hardware, UEFI, v86 browser, or recoverable memory faults.

## Safe failure and next steps

A missing IDT or invalid gate during installation must not allow continued execution. An unexpected fault is logged then enters a disabled-interrupt halt loop. The next M3 work is **TSS/IST for reliable double-fault handling**, explicit virtual-memory map/unmap operations with invalid-mapping tests, ownership and resource exhaustion, then carefully scoped interrupt-driven console I/O. Do not enable IRQs merely because CPU exceptions are registered.

Official references: [Intel SDM](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) and [GCC x86 interrupt function ABI](https://gcc.gnu.org/onlinedocs/gcc/x86-Function-Attributes.html).
