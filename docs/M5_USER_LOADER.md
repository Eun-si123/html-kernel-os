# M5-C1 — ROMFS user executable (QEMU Ring 3)

**Status:** local mini-PC genuine BIOS QEMU and GCC UBSan PASS; PR-head GitHub Actions and merge not yet verified. This is a narrowly scoped experimental loading slice, not a full OS or completed M5.

## Native execution

1. `--exception-idt --tss-ist --user-loader-probe` builds a separate relocation-free x86-64 `.text` program from `examples/user-programs/hello.S` using GCC and objcopy. It is independent of HTML-generated kernel source. The build rejects relocations, symlinks and oversized code.
2. The builder packages `/apps/hello.hke` into a temporary copy of the existing M5-A ROMFS and produces a native ELF kernel. No source assets are modified. `--user-app-source` selects another trusted assembly file; `--user-app-image` embeds prebuilt bytes for tests; the flags are exclusive.
3. The kernel reads the **actual ROMFS bytes** through `htmlk_romfs_read`, validates a fixed HKEX header, then copies the code into a private physical page. Existing M4-C1 paging helpers create user RO code at `0x400000000000`, RW zeroed stack and supervisor-only inherited kernel mappings.
4. Real CPU `iretq` enters CPL3. INT 0x80 accepts three restricted register-only operations: syscall 0 (`rdi=0x1234`) stack proof, syscall 2 (`rdi=0..9999`) numeric report, and syscall 1 (`rdi=0`) exit. Both selectors, RIP, RSP and syscall order are checked. The kernel reclaims all six tagged frames after exit and executes the original HTML source-generated kernel.
5. Actual QEMU negative tests reject malformed images **before** Ring 3 (exit 53); an unknown syscall also exits 53; unauthorized CPL3 `OUTB` causes real CPU #GP and non-success exit 45. No default boot, site, or other M4/M5 opt-in mode is changed.

## HKEX format (not ELF)

The file must be `32 + code_length <= 4096` bytes, x86-64, and have an exact little-endian header:

| Offset | Size | Rule |
| --- | --- | --- |
| 0 | 4 | ASCII `HKEX` |
| 4 | 1 | version 1 |
| 5 | 1 | header size 32 |
| 6 | 2 | flags zero |
| 8 | 4 | entry offset zero |
| 12 | 4 | code length 1..4064, exact file match |
| 16 | 4 | FNV-1a 32-bit code checksum |
| 20 | 12 | reserved bytes all zero |
| 32 | code length | relocation-free executable machine code |

FNV-1a is **not** a cryptographic signature or machine-code safety proof. Input files are trusted **at build time**, not installed by untrusted user processes at runtime.

## Reproduction

```sh
python3 -m unittest tests.test_user_image -v
python3 scripts/test_m5_user_loader.py
python3 scripts/build_boot.py --exception-idt --tss-ist --user-loader-probe --out build/html-kernel-m5-user.iso
```

Host tests verify byte-for-byte deterministic image generation, relocation detection, header/length/hash/invalid field rejection with GCC UBSan -O0/-O3. Real BIOS QEMU runs the image three times, then independently mutates both the user assembly (value 2026 -> 2027) and HTML kernel source, checks different ISO bytes and exact guest outputs, rejects four damaged images, rejects unknown syscalls, and observes the actual forbidden-I/O #GP. The original C1 fixed assembly payload symbol is absent in this M5 image.

## Limitations and next gates

The supported payload is x86-64 **assembly**, not an HTML-source user application. No standard ELF/PE, dynamic executable relocations, signature verification, runtime disk, console `run`, generic user pointer copyin/copyout, process-fault recovery, NX stack, SMP, FPU/FS-GS, UEFI or physical hardware is claimed. The current `int 0x80` ABI only accepts three tiny demo operations and does not accept arbitrary user memory pointers.

M5-C2 needs a more general reusable program ABI and error containment. M5-D must combine the real M5-B interactive UART console with a selectable user program and demonstrate both valid and invalid commands/programs. M4-D remains a bounded experiment rather than a production scheduler. Neither M4 nor M5 full milestone is completed by this slice.
