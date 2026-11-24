# M2-UX7-B1 — experimental native TinyCC HKEX backend with byte-exact HTML proof

**Local worktree; PR-head CI, merge and deployment are separate gates.**
This enables a second, explicitly selected **native Linux TinyCC backend** for HTML Kernel Language→x86-64 ELF→single-page HKEX, preserving the original GCC backend unchanged. This is *not* TinyCC running in browser WebAssembly.

## How to build and prove the image

Install a trusted x86-64 TinyCC 0.9.27-compatible executable, along with the project's existing `gcc`, `ld`, `readelf`, `objcopy`, QEMU, xorriso and Limine native build prerequisites. To reproduce on Ubuntu:

```sh
sudo apt-get install -y tcc
python3 scripts/build_tcc_html_user_image.py \
  --source examples/user-programs/html-message.html \
  --out build/message-tcc.hke
python3 scripts/build_boot.py --exception-idt --tss-ist \
  --romfs-run-console --user-fault-recover --user-timeout \
  --user-app-image build/message-tcc.hke \
  --user-app-html-proof examples/user-programs/html-message.html \
  --user-app-tcc-proof --test-exit \
  --out build/message-tcc.iso
python3 scripts/test_tcc_user_proof.py
```

The opt-in flag `--user-app-tcc-proof` may only be used with an explicit HTML source and a prebuilt HKEX image. The boot builder snapshots the HTML, **regenerates the entire HKEX using the chosen TCC backend**, compares all bytes against the supplied image and **fails closed before ISO generation** if anything differs. It cannot be used to impersonate the existing GCC byte-exact HTML proof. It also requires **guarded interactive exception recovery with real x2APIC Ring 3 timeout**; no blanket user-mode capability toggle is added.

## Compatibility and strict image constraints

- The same canonical typed Python `compile_html(target='user')` generates the initial x86-64 C. TinyCC 0.9.27 does not recognize `__builtin_unreachable()`, so a **private generated-C compatibility copy only** substitutes an actual `UD2` instruction at these compiler-known terminal sites. The authoritative compiler output/grammar and GCC path stay untouched.
- TinyCC normally places even `static const unsigned char message[]` into writable `.data`. The **compiler-generated static text array only** receives `__attribute__((section(".rodata")))` in that private copy; the current linker maps this read-only section into the existing executable **RX code page**, never a new writable user page. Arbitrary external C is not accepted.
- A purposely tiny `scripts/tcc-freestanding/stdint.h` supplies only the fixed-width x86-64 integer declarations/macros used by generated HTMLK C; **TinyCC is invoked with `-nostdinc`** and does not use host libc headers or libc objects. This is preparation for a future browser cross-compiler, not an implementation of it.
- TinyCC may synthesize a call to `memset` for local array initialization. The adapter accepts **exactly this one external symbol** and links the tiny repository-owned, freestanding `scripts/tcc-freestanding/runtime.c` byte-clearing routine without libc. Unknown external functions (`memcpy`, compiler helper calls, etc.) are rejected. This runtime object is subject to the same relocation and no-writable-data checks.
- The pre-link relocatable object must be **ELF64 x86-64**, with only `R_X86_64_PC32`/`R_X86_64_PLT32` relocations, an executable `.text`, optional read-only `.rodata`, and **no nonempty `.data`, `.bss` or other allocated sections**. The final ELF must have **only an executable `.text`** and **no relocations**. Extracted code must fit **1–4064 bytes**. Packaging uses the original 32-byte HKEX header, bounds and FNV checksum; no new disk format or kernel page permissions are introduced.
- The kernel build only permits these TCC proof flags with a guarded TSS/IDT, user fault recovery and x2APIC task timeout. In QEMU the timer readiness marker is sent to **E9 debugcon**, not the guest's COM1 text stream. The COM1 shell and captured debug port must be verified separately.

## Independent genuine QEMU results

An independently extracted Linux TinyCC binary (Ubuntu package `0.9.27+git20200814.62c30a4a-2build1`; no system installation) generated the following user images. All were created from typed HTMLK C, linked with the actual `scripts/user_program_entry.S` and `scripts/user_program.ld`, verified relocation-free, packaged with the native HKEX code and booted as real guest CPL3 processes in **QEMU `qemu64,+x2apic`**. Each guest returned to a live COM1 shell, proved TCC HTML source/image byte identity, ran with a real M5-E2 timeout marker on E9, and reclaimed six user frames:

| Source | User HKEX bytes | Observed actual CPU result |
| --- | ---: | --- |
| `html-message.html` | 331 | Exact text `Hello from HTML user mode!` |
| `html-multireport.html` | 389 | Exact text `tick` twice, numeric `2026` |
| `html-u64-report.html` | 339 | `4294967296` twice, then `18446744073709551615`, exit status 7 |
| `human-agent-program.html` | 388 | Custom function result `6` three times, then `4294967296` |
| `html-tcc-stress.html` | 977 | Checked array sum `14`, wide division `4611686018427387904`, bounded `while` final result `3` |
| Modified editor HTML `value="2031"` | 267 | `2031`, not 2026; **changed binary bytes** |

Negative native acceptance checks reject mismatched HTML/HKEX byte proof, attempting to pass a TCC binary through the legacy GCC proof, and omitting guarded timer requirements; unit checks reject symlinked input/output, oversized source, non-PC-relative object relocations, writable allocated data, unsupported source headers/ABI, and unknown allocated sections. Real guest verification is distinct from host-only unit tests.

## Why this is not the final browser-native compiler

The TCC executable, GNU linker and ELF tools above run **on Linux**, not in GitHub Pages. Existing M2-UX7-A browser Pyodide compiles HTMLK→real C, but **the browser still cannot itself generate an ELF/HKEX, update the ISO, or boot the newly generated code**. The native proof described here makes the next WASM cross-compiler path explicit and experimentally checks correct semantics on real x86-64 CPU simulation. An actual WASM x86-64 TCC build, browser linking/packing and real browser source→new guest binary still require dedicated implementation and adversarial testing (Issue #112).

Additional limitations: TCC version/architecture/codegen can change between installations, so **the entire binary is checked against a rebuild in the *same environment***; this is a reproducibility/consistency proof, **not a cryptographic signature**, malware sandbox, or proof that arbitrary user assembly is safe. The current user code page remains RX, kernel protected; physical M6 remains NOT RUN.
