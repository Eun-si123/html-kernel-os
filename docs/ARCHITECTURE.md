# Architecture / evidence ledger

## Goal

Write kernel *logic* in a constrained HTML-like language. Translate it ahead of time to a freestanding native target, and eventually boot that target without a browser or host OS.

## What exists now

1. The Python stdlib HTMLParser validates a deliberately tiny grammar:
   - exactly one outer kernel element with x86_64 architecture;
   - one onboot block;
   - one or more print nodes (literal UTF-8 text up to 4096 bytes, or unsigned numeric output);
   - unsigned 64-bit let/set, bounded repeat and comparison-based if blocks (M2 subset);
   - optional final halt;
   - no scripts, nested elements inside print, unknown attributes, or arbitrary HTML.
2. Code generation emits freestanding C source with a kernel_main() function.
3. Generated code initializes and outputs to COM1 at 0x3f8 alongside QEMU debugcon port 0xE9. Both outputs were seen in local QEMU boot. This is not VGA/framebuffer or a general hardware driver.
4. The original M0 pipeline compiles an object; the new `scripts/build_boot.py` links that object to the tiny Limine protocol handoff (`boot/kernel_entry.c`) using `boot/linker.ld` and packs a hybrid BIOS/UEFI ISO. BIOS x86-64 QEMU boot PASS locally and in GitHub CI with source provenance and negative controls. Live browser emulation PASS in one Chromium/Playwright session; UEFI and real PC boot are NOT yet verified.

## M2 compiler architecture (partial)

The new compiler/language.py performs strict HTML-shaped parsing into a small typed statement tree and validates expressions through a restricted Python AST (parsed but **never evaluated as Python code**). compiler/htmlk.py lowers accepted numeric and text operations to freestanding x86-64 C. Unsigned u32/u64 and signed i32/i64 arithmetic are explicitly modulo 2^32/2^64. Generated C uses unsigned intermediate bit patterns and defined sign reinterpretation helpers from `compiler/numeric_types.py` to prevent C signed-overflow undefined behavior (tested with independent UBSan -O0/-O3), while typed values/variables/params/returns track both width and signedness and reject implicit conversions. Unsigned bitwise/shifts use helpers that return zero on overshift. Proposed M2 integer division/remainder emits explicit typed helpers: a run-time zero divisor takes a target-specific fatal path (Linux stderr+exit 65; kernel debugcon/COM1+halt and non-success debug-exit), while signed minimum/-1 is handled before invoking C division so it never triggers signed-division undefined behavior. Bounded repeat supports nearest-loop break/continue; nested source-work/output budgets remain conservative. Typed functions support scoped bodies. `compiler/function_codegen.py` resolves lexical bindings to unique native C locals, validates typed expressions, branches, bounded loops and final returns, then generates function definitions for both targets. Fixed-size, zero-initialized typed arrays with checked read/write indexes are implemented as compiler-owned C arrays in the proposed M2 extension; accesses cannot expose a raw pointer through the source-language grammar. Compiler-emitted bounds failures terminate Linux or the test kernel with distinct fault statuses. No virtual-memory isolation is implied. A bounded non-recursive call graph tracks nested source work and compile-time recursion/depth constraints. `if` optionally holds one final `<else>` child; both branches are checked for expressions, local scope and conservative worst-case output/work limits before native code generation. Function bodies have no global state or I/O; local `set` is permitted. This code runs inside the real M1 boot image, not in a browser/Python runtime. See [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md).

## Linux userland backend (minimal P2, not a distribution)

The same strict language parser and validated statement tree can generate either a freestanding x86-64 kernel entry or a Linux userspace main function. The Linux backend sends output bytes to standard C putchar and flushes stdout before returning a normal exit status, **never privileged port I/O / cli / hlt**. The kernel backend preserves Limine handoff and COM1/debugcon output. A shared source produces the same arithmetic and branch behavior on both targets. See [STATUS.md](STATUS.md) and [VALIDATION.md](VALIDATION.md).

## M4-C1 native user/kernel boundary (opt-in, single task)

The QEMU-only M4-C1 probe is deliberately **separate from M4-B2 timer preemption**. `boot/user_probe.c` reuses the M3 verified Limine memory map/HHDM and tagged frame-owner pool for six bounded pages, copies only the PML4 (never mutating bootloader CR3), removes U/S from inherited mappings and wires user RO code and RW stack into a reserved private PML4 slot via `boot/user_pages.c`. The existing TSS/IST GDT is extended only under `HTMLK_M4_USER_PROBE` with Ring-3 CS/SS and a dedicated CPL0 RSP0 syscall stack; #DF and #PF emergency stacks remain independent. `boot/user_entry.S` enters Ring 3 with iretq, runs fixed test code, traps to a DPL3 INT 0x80 gate whose C dispatch validates saved user CS/SS/RIP/RSP and numeric syscall ID, returns to user via iretq, then restores original CR3 and main kernel stack for bounded frame reclamation. CPU #GP on privileged port I/O and #PF with precise CR2/error codes on kernel memory read and RO user-code write prove the boundary in real QEMU. Faults remain **fail-stop**, no surviving second process or general loader. See [M4_RING3_C1.md](M4_RING3_C1.md); this does not complete M4.

## M4-C2 two-task fault containment (opt-in)

The kernel allocates two separate six-frame user images with independent PML4/PDPT/PD/PT roots and code/stack backing pages while preserving the original Limine CR3. Both Ring3 payloads use the same virtual entry and stack addresses but have different physical mappings; the survivor is checked to start with a zeroed stack independent of the offender. M3 #PF and #GP handlers use a strict pure predicate from boot/isolation_policy.c to accept only the single intended Ring3 fault with a matching selector, vector, error, RIP/RSP, CR2 and active CR3. The C1 assembly return restores the original supervisor CR3 and trusted main stack before releasing the faulty task frames. B then runs and exits via INT0x80; all frames are reclaimed before generated HTML executes. All other faults fail-stop. This is sequential task containment, not interrupt-driven user preemption or a general-purpose process loader. [M4-C2 proof](M4_FAULT_ISOLATION.md).

## M4-D user preemption, CR3/TSS ownership and fault retirement (opt-in)

Independent one-vCPU x2APIC timer path uses two trusted never-yielding CPL3 task images. Each has its own tagged private 4-level page-tree root, user code/stack, 16KiB ring0 IRQ stack, and a distinct saved full-GPR x86-64 interrupt frame. Switching tasks validates stack bounds, userspace CS/SS/RIP/RSP and register sentinels, loads TSS.RSP0 for the next ring3-to-kernel transfer, then loads next CR3; IRETQ resumes the previously preempted CPL3 task. When A faults, kernel validates expected PF/GP and IRQ progress, restores original root before releasing only A's owned frames, resumes B from its saved CPU interrupt context, then returns to original kernel and generated HTML. No generic process runtime, user syscall under live IRQ preemption, FPU/SIMD context, SMP, UEFI or hardware proof. [M4-D exact validation](M4_RING3_PREEMPT.md).

## Boundaries

- HTML is being used as **syntax**, not as the web platform. The meaning of each tag is custom.
- Python runs only at build time; the generated machine code does not depend on Python or JavaScript.
- C currently acts as a portable intermediate representation. The objective is not to claim that C has disappeared from the build toolchain.
- The pinned Limine protocol and linker layout are verified in BIOS QEMU, but not in UEFI or on physical hardware.
- Native x86 instructions do not automatically make the result safe or portable to real machines.

## Risks and engineering decisions

- A multi-purpose HTML renderer is **not** needed for compiling the source.
- Freestanding compiler output is not itself a functional kernel; boot handoff, privilege state, interrupt state, and runtime support must be designed.
- debugcon is a development-only output channel. Standard device support needs additional code.
- Compiler validation must reject unsupported constructs predictably.
- Run reproducible QEMU boot tests in CI on every relevant change; only claim the exact platform tested.
- Reevaluate syntax ergonomics before expanding the grammar; do not introduce faux-HTML tags without a clear low-level semantic contract.

## M1 boot integration (implemented and verified; evidence in STATUS)

- Pin a specific Limine release, with checksum/provenance.
- Add correct Limine request structures and a linker script targeting x86_64.
- Compile HTML-derived object together with a tiny handoff shim only where unavoidable.
- Build a bootable image and run QEMU using explicit machine type and debugcon redirection.
- Assert the exact debug output and a deterministic halt/exit condition in CI.
- Label success only as "bootable demo kernel", not "operating system complete".

## M3 — first opt-in Limine memory map handoff (partial)

The pinned Limine protocol's memory-map and HHDM requests are issued **only** when `--memory-probe` explicitly enables `HTMLK_M3_MEMORY_PROBE`. The pure freestanding C11 `boot/page_pool.c` rejects malformed, overlapping or oversized boot maps and selects 16 x 4KiB pages exclusively from USABLE ranges, never page zero. `boot/memory_probe.c` reads the actual Limine memory-map response, uses HHDM to write/read sentinels into those pages under BIOS QEMU, verifies exhaustion without reuse, and halts with a distinct error on malformed input or RAM mismatch. The ordinary boot path has no new memory access. This is not virtual mapping, general heap allocation, fault handling or a proof of memory isolation. See [M3_MEMORY_BOOTSTRAP.md](M3_MEMORY_BOOTSTRAP.md).

## M3 native framebuffer text output (PR #39, opt-in)

With `--video-console` the kernel also requests a Limine 32-bit RGB framebuffer and `boot/console_fb.c` rasterizes the source program's `<print>` bytes into direct-mapped RGB pixel memory while preserving COM1 and debugcon output. Invalid format or buffer metadata causes a no-op screen path, **not** a pointer escape to HTML programs. A QEMU guest-side pixel readback and a host QEMU HMP `screendump` with independent pixel-value assertions demonstrate real video data on BIOS emulation; this is NOT a browser v86/hardware, Unicode, keyboard, interrupt or MMU proof. Compiler boot flags now enforce the x86-64 baseline ISA after a guest `SHLX` BMI2 illegal-instruction crash was reproduced and corrected. See [M3_FRAMEBUFFER_CONSOLE.md](M3_FRAMEBUFFER_CONSOLE.md).

## M3 CPU exception IDT (PR #40, opt-in fail-stop)

`--exception-idt` enables `boot/exception_idt.c` at build time. On the real Limine x86-64 boot path, the ring-0 entry reads the current CS selector, builds 16-byte IDT gates for all CPU-defined exception vectors 0–31, and executes `lidt` with IF masked before any HTML kernel code or other optional probes. Handlers use GCC's documented `interrupt` ABI and separate no-error-code/error-code signatures, with the freestanding compile flags `-mgeneral-regs-only -mno-red-zone -march=x86-64`. An exception logs vector, RIP, error and PF CR2 through debugcon+COM1, then halts; test images signal QEMU non-success 45. True CPU faults for vectors 0, 6, 13, 14 were triggered and checked under BIOS QEMU (source mutation and map/video composition included). TSS/IST, nested interrupt safety, external hardware IRQ, page-table mapping/recovery, user mode and physical PC compatibility remain unimplemented. See [M3_EXCEPTION_IDT.md](M3_EXCEPTION_IDT.md).

## M3 private x86-64 four-level address translation (PR #41, experimental)

With `--paging-probe`, the Limine memory-map+HHDM requests supply an existing USABLE 16-frame page pool. Five distinct pages hold a private PML4 copy, new PDPT, PD, PT and mapped data. Only a previously-empty slot 320 is used; no modifications are made to Limine's original CR3 root. The pure `boot/paging_tables.c` helper validates physical frame addresses and non-user-accessible leaf flags. `boot/paging_probe.c` switches to private CR3, reads/writes a canonical fixed virtual alias, verifies the HHDM physical alias, clears its PTE, issues `invlpg`, restores original CR3 and executes HTML-derived code. A separate test-only real #PF after the unmap is caught by the M3 IDT. This is four-level-only, single-CPU, no TSS/IST, page allocator ownership, page-fault recovery, process isolation, or general virtual API. See [M3_PRIVATE_PAGING.md](M3_PRIVATE_PAGING.md).

## M3 one-shot lazy CPU fault recovery and owned frames (PR #44, opt-in)

The limited Limine USABLE 16-page pool is now consumed via a pure freestanding owner-tagged frame registry. TABLE and DATA frames are never conflated; wrong owner, double free and exhaustion are rejected. With `HTMLK_M3_PAGING_RECOVER_TEST` and the prior IDT installed, a genuine not-present supervisor read of a single exact private CR3 alias may be recovered **once**: the #PF handler checks CR2, error bits and active CR3, claims a DATA frame, zeroes it via HHDM, maps a supervisor-only PTE and returns through `iretq`. The CPU retries the original instruction; normal code validates zero initialization, the HHDM physical alias, and page-table Accessed/Dirty-bit-safe constraints. After unmap and original CR3 restoration, all frame ownership is released. All other page faults remain fail-stop. No general process memory, TSS/IST, external IRQ, SMP, or unbounded page fault recovery is provided. [M3_FAULT_RECOVERY.md](M3_FAULT_RECOVERY.md).

## M3 native x86-64 TSS and exception IST separation (PR #45, opt-in)

The kernel can optionally build a private long-mode GDT containing ring0 code/data and a 16-byte available-TSS descriptor. It reloads code/data selectors, performs privileged `ltr`, and then constructs the standard CPU IDT with IST=1 for vector8 (#DF) and IST=2 for vector14 (#PF). The TSS supplies two distinct 16KiB aligned kernel-resident stacks. A test-only corrupted IST2 pointer causes a *real* #DF during a genuine #PF delivery, and the emergency IST1 handler identifies its current RSP before fail-stopping; a normal PF uses IST2. Previous restricted one-shot recovery continues on IST2 with actual `iretq`, and video/physical pool/private mapping still work. There is no per-core TSS, user-space I/O bitmap support, IRQ enable/dispatch, or production exception hierarchy. [M3_TSS_IST.md](M3_TSS_IST.md).

## M3 bounded multi-page map/unmap and physical owner reclamation (PR #47)

The prior private CR3 holds a caller-owned PT, and `htmlk_paging_leaf_map/unmap` in `boot/paging_tables.c` operate only on that validated 512-entry leaf page. Map rejects duplicate/occupied/unaligned/out-of-range frames; unmap requires the expected physical frame. Caller must invalidate the TLB with `invlpg` before freeing the frame to the owner registry. In real QEMU the kernel maps three additional supervisor-only virtual 4KiB offsets, reads/writes via CPU and HHDM, then unmaps/reuses the same frames for three complete cycles. A revoked second alias must produce actual CPU #PF with matching CR2, while preapproved first-alias #PF recovery and IST stack switches continue working. This is not unrestricted VM ownership, ring3 isolation or a heap. [M3_MULTIPAGE.md](M3_MULTIPAGE.md).
