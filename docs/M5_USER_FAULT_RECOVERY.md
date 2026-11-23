# M5-E1 — guarded real CPL3 CPU fault recovery back to live UART shell

**Status:** opt-in, local x86-64 BIOS QEMU/host UBSan proof PASS. Exact PR-head GitHub Actions/security and merge are **not yet verified**. This is bounded recovery for a *known active* Ring3 application, not safe execution of arbitrary untrusted code or the full M5-E timer budget.

## Reproduce

```sh
python3 -m unittest tests.test_user_fault_policy tests.test_console_runner -v
python3 scripts/test_m5_user_fault_recovery.py
python3 scripts/build_boot.py --exception-idt --tss-ist --romfs-run-console --user-fault-recover --out build/html-kernel-m5-recovery.iso
# In an Ubuntu interactive terminal with QEMU, GCC and xorriso:
python3 scripts/run_m5_console.py --with-user-program --recover-user-faults
```

The opt-in builder adds *only* in this mode four additional compiled source programs under immutable ROMFS: `fault-io.hke` (actual Ring3 privileged `OUTB` → CPU #GP error 0), `fault-pf.hke` (actual user read of supervisor virtual address → CPU #PF error 5 on IST2), `fault-ro.hke` (actual user write into protected RO code page → CPU #PF error 7 on IST2), and `fault-ud.hke` (actual `UD2` opcode → CPU #UD). The valid existing `/apps/hello.hke` remains available, and neither default boot nor M5-D1 builds contain these recovery behaviors.

## Runtime guard and recovery contract

- After real COM1 `run /apps/fault-*.hke`, the guest executes the image in native CPL3 through the existing M5-C1 private CR3 / RO code / RW stack mapping, not a simulated CPU exception. `boot/exception_idt.c` handles **only** vectors 6, 13, 14 when explicitly enabled; all other exceptions and legacy modes remain fail-stop.
- Before abandoning a task the new pure `boot/user_fault_policy.c` guard verifies expected Ring3 CS/SS, executable RIP interval, user RSP interval, RFLAGS reserved/IOPL/NT/VM restrictions, exact current private CR3 ownership and architectural user error-bit requirements. The caller additionally requires an active selected program, original safe kernel stack/CR3, exactly six owned frames, no previous fault and no completed exit. #PF must have a genuine IST2 stack. *CPL0 faults never access unprovided user RSP/SS fields* and are not accepted as a user fault.
- For a valid active task fault, the existing trusted `htmlk_m4_user_return()` restores the original Limine kernel CR3/main stack; the existing tagged frame registry releases **all six** code, stack and page-table frames on that safe stack. The active shell prints `M5_ERR_USER_FAULT`, then another genuine UART `M5_PROMPT>`. Normal successful user program exit is unchanged.
- `scripts/test_m5_user_fault_recovery.py` boots the real image **three times**, performs all four actual CPU fault paths, and after **each** executes `/apps/hello.hke` successfully in the same boot. It asserts four fault markers and four explicit reclamations per repetition, two IST2 proofs, COM1 output, and clean shell `exit`. Further genuine QEMU scenarios independently mutate HTML source and the standalone user assembly to change their ISO bytes and observed CPU output, check no-input idle and reject invalid builder combinations.
- **Additional M5-E1 syscall isolation:** after strict Ring3 CS/SS, executable RIP, private-stack, current CR3, IOPL and six-frame ownership checks, any unsupported `int 0x80` ID or invalid parameter **terminates only the active user task**. The existing safe kernel CR3/stack restoration and six-frame reclaim path is reused; the UART shell emits `M5_ERR_USER_SYSCALL` and stays interactive. In separate native QEMU builds, both an unknown syscall ID and an invalid numeric argument are executed as real user instructions in `run /apps/hello.hke`; each is preceded and followed by execution of an independent valid `/good.hke`, a working `help`, and clean shell `exit`. A process syscall protocol violation is distinguished from a CPU #GP/#PF/#UD (reported as `M5_ERR_USER_FAULT`). Standalone older M4-C1 and M5-C1 probes retain their original fail-stop syscall behavior. This is **not a full syscall ABI** and does not accept arbitrary user pointers.
- Host UBSan `-O0/-O3` tests reject forged kernel CS/SS, wrong CR3, corrupted RFLAGS, invalid RIP/RSP, too-large images and invalid #PF/other exception codes before entering the guest.

## Still not supported (M5-E2 and later)

**No timer-based CPU budget or timeout!** A valid but infinitely spinning CPL3 program can hang the entire shell, because the M5-D1 loader uses disabled timer interrupts. The verified M4-D x2APIC preemption/fault isolation is a separate test mode and is **not** integrated here. No general syscall input pointer checking, multi-program concurrency, user FPU/FS/GS/SMP context, ELF loader, writable disks, USB keyboards, calibrated APIC timer, UEFI, physical hardware or strong security boundary. FNV checksum is not an authenticity mechanism; run only trusted compile-time programs. Kernel-origin and unarmed faults are fail-stop, not repaired. M5-E2 and M5-E3 acceptance are tracked in [Issue #75](https://github.com/Eun-si123/html-kernel-os/issues/75).
