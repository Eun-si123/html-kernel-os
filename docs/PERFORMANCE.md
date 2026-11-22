# Performance contract — native C++/Rust-class ambition

**Status:** project performance **goal**, not observed performance or a release claim.

## Plain-language goal / 한국어 설명

HTML Kernel 언어는 **Python처럼 배우기 쉽고, C++·Rust에 가까운 네이티브 성능**을 목표로 해. HTML 태그는 소스 문법일 뿐, 실행 때마다 브라우저 또는 인터프리터가 태그를 해석하도록 만들 필요는 없어.

- **Confirmed owner preference:** fast ahead-of-time (AOT) compiled native programs, without a mandatory browser/JavaScript/Python interpreter at target runtime.
- **Not confirmed:** percentage of C++/Rust performance, particular LLVM backend, or a specific target benchmark threshold.
- **Current implementation:** `compiler/htmlk.py` emits freestanding C, and the compiler toolchain can emit an x86-64 object. Only literal print/halt constructs exist. **No meaningful CPU-bound performance comparison is possible yet.**
- Build-time Python and C are permitted during prototyping; runtime dependencies must be disclosed and justified.

## Engineering requirements

1. **Native/AOT by default:** compilation happens before execution. Do not silently introduce per-tag interpretation, browser runtime, Python VM, or garbage collector into kernel hot paths.
2. **Use a real optimizing backend:** for the current C-as-IR prototype, ensure normal native compilation at `-O2` works. Consider LLVM IR/native lowering only when measured benefits justify complexity. `-O3` is an experiment, not an automatic upgrade.
3. **Zero avoidable abstraction overhead:** simple arithmetic, branching, function calls, and memory accesses should lower to direct native operations. Prefer inline/monomorphized small generic constructs where tests show a benefit; do not promise absolute zero overhead.
4. **Safety must survive optimization:** explicit type widths, overflow policy, alignment, aliasing/ownership, pointer privileges, atomics and concurrency semantics are requirements for fast **correct** code. Do not rely on undefined behavior or unchecked user I/O to win benchmarks.
5. **Runtime vs build-time costs:** track executable code size, runtime RAM use, CPU time, tail latency, and compile time separately. Boot latency, interrupt cost, binary size and debugging also matter for an OS.
6. **No fabricated speedups:** never label code “as fast as Rust/C++” from a compiler's brand, generated assembly, constant-folded empty loops, or QEMU execution time.

## Evaluation when expressive language constructs exist (M2+)

Use **equivalent** kernels/programs in HTML Kernel, C++ and Rust. Match algorithm, integer semantics, inputs, output checks, allocation strategy and external I/O. Compile with documented stable toolchain versions and comparable `-O2` / release configurations on the **same** CPU architecture and target-feature level.

Initial representative workloads:

| Category | What to measure | Confounders to control |
| --- | --- | --- |
| Integer arithmetic and control flow | cycles / throughput, correctness | overflow semantics, dead-code elimination, constant folding |
| Array iteration and memory access | bytes processed/s, cache misses | layout, bounds checks, alignment, vectorization, memory size |
| Functions, recursion and calls | throughput, code size | inlining decisions, recursion depth, calls optimized away |
| Allocations and ownership | operations/s, peak memory | allocator policy, allocation pattern, cleanup |
| Kernel-specific (after M3/M4) | context switch, syscall/interrupt latency | QEMU overhead, privilege level, scheduler, tracing, timer |

## Reproducible benchmarking procedure

1. **Before timing**, validate identical outputs/checksums, test edge cases and keep work observable so optimizing compilers cannot eliminate it.
2. Capture OS/firmware/CPU/microcode, power state, clock behavior, build options, compiler versions, commit SHA and input sizes; warm up where appropriate.
3. Run repeated independent trials under controlled conditions, report medians and variability, optionally p95 for latency, plus raw data and scripts. Repeat in shuffled order and treat noise as uncertainty.
4. Compare each measured implementation with both baselines, and investigate regressions in generated code, unsafe assumptions and unnecessary runtime work. Record meaningful differences but **do not choose or claim an arbitrary percentage before a baseline exists**.
5. Separate **QEMU functional tests** from native-machine performance measurements. Never compare QEMU timing with native C++/Rust results and claim language parity.
6. If an optimization improves speed but breaks correctness, memory safety, reproducibility, or practical build/debug cost, it is a failed change.

## Milestone gates / next steps

- **M1:** ensure the HTML-generated code boots in QEMU; also build an optimized native object. This is a compile/boot check **not a speed benchmark**.
- **M2:** implement sufficient typed language constructs for first like-for-like C++/Rust benchmarks; publish reproducible harness and measurements **before** a numerical performance claim.
- **M3–M6:** evaluate allocator, memory, syscall, scheduler and physical-device performance as each is implemented; preserve correctness and safety gates.

Current status: **NOT BENCHMARKED**. Any measured performance statement needs exact code and test evidence in [STATUS.md](STATUS.md), per [VALIDATION.md](VALIDATION.md).

## References

- [Clang optimization options](https://clang.llvm.org/docs/CommandGuide/clang.html)
- [The Rust Performance Book — Benchmarking](https://nnethercote.github.io/perf-book/benchmarking.html)
- [Cargo benchmarking](https://doc.rust-lang.org/cargo/commands/cargo-bench.html)
