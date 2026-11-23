# M5-A — bounded read-only embedded filesystem (opt-in)

**Status:** merged as PR [#62](https://github.com/Eun-si123/html-kernel-os/pull/62) at main commit `4512f1d`. Actual QEMU BIOS, host UBSan and GitHub Actions PR run `45121533786` / merged-main run `45121995144` PASS; merged-main Gitleaks run `45121995124` PASS. This is a **preparatory M5 slice**, not completion of M4 or M5.

## Architecture and limitations

- `examples/romfs/` contains two example files, `/welcome.txt` and `/config/build.txt`. The build-time Python generator `scripts/gen_romfs.py` sorts their canonical ASCII paths and turns **the actual file bytes** into literal C arrays linked into the native kernel ELF `.rodata`. No storage device is used and **the raw files are not included as HTML files on the boot ISO**.
- `boot/romfs.c` offers a freestanding read-only API for a trusted immutable table. It validates 1–16 strictly sorted, unique canonical paths, no `.`/`..` segments, no path traversal, no symlink inputs, at most 4 KiB per file and 32 KiB total. Reads copy only the bounded `min(capacity, length-offset)` and return zero bytes at EOF, including `SIZE_MAX`; missing or invalid paths return `false` with zero bytes. Files can contain any binary bytes, but this **console proof** only prints basic ASCII and newline.
- `--romfs-probe` enables an independent x86-64 Limine/QEMU boot path. In real guest CPU execution `boot/romfs_probe.c` reads each file in 13-byte chunks, prints native debugcon/COM1 output, rejects traversal and missing files, then proceeds into **HTML-generated** `kernel_main`. Normal images have no ROMFS code or payload linked.
- `--romfs-negative --test-exit` intentionally exits via QEMU `isa-debug-exit` code 57 *after* path-denial assertions, without running the HTML kernel. It is an explicit negative test image, not a crash recovery mechanism. All unrelated test flags are rejected when `--romfs-probe` is selected.
- This is **not** disk or FAT/EXT support, a mounted initrd, writable filesystem, a generic VFS, syscall-based file I/O, an executable program loader, terminal input, dynamic kernel heap, or CPL3 isolation. Kernel-owned C pointers are trusted; the API does **not** accept arbitrary user pointers. There is no protection against memory corruption inside the privileged kernel.

## Reproduce on an Ubuntu host with `gcc`, `qemu-system-x86_64`, `xorriso` and pinned Limine cache

```sh
python3 -m unittest tests.test_romfs_generator -v
for opt in 0 3; do
  gcc -std=c11 -O${opt} -fsanitize=undefined -fno-sanitize-recover=all -Wall -Wextra -Werror -I boot boot/romfs.c tests/native/test_romfs.c -o build/romfs-test-${opt}
  build/romfs-test-${opt}
done
python3 scripts/test_m5_romfs.py
python3 scripts/build_boot.py --romfs-probe --out build/html-kernel-m5-romfs.iso
```

The native test builds and boots actual BIOS ISOs with QEMU exit checks: original HTML + original ROMFS, **only changed ROMFS file** in a rebuilt ISO, **only changed HTML source** in a rebuilt ISO, then a fail-closed negative image. Each case asserts the exact COM1/debugcon payload and ISO difference; bad flag combinations must be rejected before building. This is stronger than a static source test but **not physical hardware execution**.

## Remaining M5 phases / gates

- **M5-B:** implemented as opt-in **real 16550 COM1 UART input** with `help`/`ls`/`cat`/`exit`, independently QEMU/CI-verified in [M5-B proof](M5_SERIAL_CONSOLE.md) and merged in PR #66. No USB/physical keyboard has been verified.
- **M5-C:** independent user program image and bounded loader using proven M4-D memory/privilege protection; reject invalid ELF/bad syscall/user pointers without kernel panic.
- **M5-D:** native interactive sequence `command → read ROMFS file → run separate program → invalid command rejected` with QEMU repeatability and clear rollback, before claiming M5 complete.

**Dependency:** M4-D independently verified user-mode scheduling and fault isolation. M5-A can be built/tested separately while M4-D remains open; it must never be used to upgrade M4 status.
