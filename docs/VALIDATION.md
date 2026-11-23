# Validation and evidence classes

Prefer realistic negative tests and observable results over adding success-looking badges. Exact test outcomes must be tied to a concrete commit.

## Prototype checks (current)

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/agent_feature_map.py validate
python3 scripts/roadmap.py --check
python3 scripts/check_docs.py
python3 compiler/htmlk.py examples/kernel.html --out build/kernel.c
gcc -std=c11 -ffreestanding -fno-stack-protector -fno-pie -Wall -Wextra -Werror -c build/kernel.c -o build/kernel.o
```

A feature map's `impact` report only suggests regression files; it never runs them.

## Native boot evidence (new M1 pipeline)

```sh
python3 scripts/test_boot.py       # really boots original + changed HTML ISOs in headless QEMU
python3 scripts/build_boot.py --out build/html-kernel.iso  # normal, non-test image
```

Requires QEMU x86-64, GCC, make, xorriso, Python 3.12+; pinned Limine dependencies are SHA-256 checked. A QEMU test image exits with status 33 after verified serial/debugcon output; a normal boot image halts. Browser emulation and physical-machine tests are separate evidence classes. See [STATUS.md](STATUS.md) for observed current results and the exact CI run.

## M4-C1 Ring3 and syscall evidence (2026-11-23 local)

`python3 scripts/test_m4_user.py` builds an independent opt-in ISO using `--exception-idt --tss-ist --user-probe`; a real BIOS QEMU CPU must execute code and stack stores at CPL3, enter CPL0 through INT0x80/TSS.RSP0, return to CPL3, then exit back to the original kernel CR3 and run changed-source HTML output. The test asserts two clean normal boots and source-mutation image provenance. Negative isolates are CPU-observed: unknown syscall exits 53; attempted CPL3 OUTB emits #GP (vector13, exit45); supervisor kernel read #PF has error 0x5, CR2 0xFFFFFFFF80001000; user RO-code write #PF has error 0x7, CR2 0x0000400000000000. Both #PF events must use the M3 IST2 emergency stack. Invalid builder combinations are rejected. `tests/test_user_pages.py` runs the pure page permission helper and invalid-frame cases under GCC -O0/-O3 UBSan. These observations **do not prove safe user fault cleanup, concurrent isolated tasks, UEFI or hardware**, and no combination with M4-B2 preemption is asserted. See [M4_RING3_C1.md](M4_RING3_C1.md).

## M4-C2 bounded Ring3 task fault survival (2026-11-23 local)

Run python3 scripts/test_m4_isolation.py. Real BIOS QEMU must show two private task CR3s and original CPU exception delivery: offender A user-to-kernel memory read causes #PF error 5 with IST2, but kernel restores trusted CR3, reclaims only A frames, executes B user syscall and exit and reclaims B frames without leak, followed by exact original/modified HTML output (QEMU success 33). Alternate genuine A exceptions #GP error 0 and RO-code #PF error 7 must also preserve B. Forged CPL0 context is rejected with non-success 55; B unexpected #GP must fail-stop with non-success 45 and no success HTML output; invalid builder flag combinations fail. Host-native tests/test_isolation_policy.py must pass GCC -O0/-O3 UBSan fault-validation boundaries. This does not validate concurrent CPL3 preemption, SMP, arbitrary user loader, UEFI or physical PC. [M4-C2 details](M4_FAULT_ISOLATION.md).

## Observed QEMU and browser boot results (2026-11-22)

- Real x86-64 BIOS QEMU, source alteration and negative controls **PASS**, PR #13 CI run `45027891902`, main run `45029073618`.
- Public GitHub Pages run `45029073658` **SUCCESS**. Connected Chromium/Playwright navigated to the published `/play.html`, clicked **브라우저에서 부팅하기**, then read exact COM1 text `Hello from HTML Kernel!\nNative code, not a browser.\n` and 0 console errors. This is one browser/runtime observation; other browsers/mobile devices and physical machines remain unverified.

## M2 numeric source code acceptance (partial language implementation)

Use scripts/test_language_boot.py with QEMU to verify the committed arithmetic example and a changed expression in a *second* independently built boot image. Assert exact decimal output, the conditional changing from true to false, and invalid-source rejection. See [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md) for currently implemented syntax and unsigned 64-bit semantics.

## M2 user-defined functions — observed local proof

Run `python3 scripts/test_functions.py` to compile one HTML source into both a Linux executable and a real Limine/QEMU kernel. It checks original and modified function return expressions, exact output, conditional changes and rejects incorrect expected output and recursive calls. Run `python3 -m unittest discover -s tests -q` for malformed typed signatures, call arity, undefined functions, recursion, depth and work budgets. General function bodies and other data types remain unsupported.

## M2 browser function demo (observed on public Pages, 2026-11-22)

GitHub PR #20: [CI run 45035455198](https://github.com/Eun-si123/html-kernel-os/actions/runs/45035455198) PASS; main [CI run 45035522696](https://github.com/Eun-si123/html-kernel-os/actions/runs/45035522696) PASS. Public [Pages run 45035522693](https://github.com/Eun-si123/html-kernel-os/actions/runs/45035522693) completed build/deploy successfully. In connected Chromium/Playwright, navigated to `https://eun-si123.github.io/html-kernel-os/play.html?demo=functions-40756f`, selected `functions`, clicked `브라우저에서 부팅하기`, and observed status `선택한 HTML 커널의 실제 시리얼 출력 검증 성공!` and actual COM1 output `Functions in HTML Kernel!\n13\n17\nfunction PASS\n10\n12\n` with browser console 0 errors. One runtime proof is not proof of mobile browser, UEFI or physical machine support.

## M2 scoped function bodies (new local proof)

`python3 scripts/test_scoped_functions.py` builds and runs both an unprivileged Linux executable and a real Limine/QEMU kernel using `examples/scoped-functions-kernel.html`. It checks exact expected output (`25`, `10`, `scoped function PASS`), mutates the function condition and confirms new output (`22`, `10`), then rejects wrong-output, missing-return and out-of-scope-source negative cases. `tests/test_scoped_functions.py` checks shadowing, nearest-variable writes, lexical escapes, typed return values and runaway-work budgets. Current result: **local + CI + Chromium browser PASS**. PR #23 run `45037302129` and merged main run `45037413551` succeeded; Pages run `45037413559` built+deployed four ISOs successfully. Connected Playwright navigated to `https://eun-si123.github.io/html-kernel-os/play.html?verify=scoped-5bf56c`, selected `scoped`, clicked Boot, and captured exactly `Scoped functions in HTML Kernel!\n25\n10\nscoped function PASS\n` from COM1; console error count 0. This does not establish Android/browser-engine/physical-hardware compatibility.

## M2 if/else control-flow verification (new local proof)

Run `python3 scripts/test_else.py`: it compiles one HTML fixture into a real Limine x86-64 kernel image and a normal Linux binary, executes both, checks exactly the same serial/stdout bytes (baseline includes else branch, true/false function branches, nested if/else and bounded repetition), then mutates the else-side value (`8` to `9`) and confirms changed native output plus ISO provenance. Wrong-output expectations and orphan/duplicate else and leaked variable references are rejected in both targets. `tests/test_else.py` covers parser nesting, lexical scopes, output/work budgets, early returns and compiler CLI file+line diagnostics. Current result: **local + GitHub CI + public Chromium boot PASS**. PR #25 CI `45039571823`, merged main CI `45039645315`, and Pages build/deploy `45039645280` all succeeded. Connected Chromium/Playwright navigated to `https://eun-si123.github.io/html-kernel-os/play.html?verify=else-46e8d5`, selected `branches`, clicked Boot and read the actual COM1 bytes `HTML if/else native!\nelse branch PASS\n8\n17\n222\nnested PASS\nnested PASS\n`; the UI displayed `선택한 HTML 커널의 실제 시리얼 출력 검증 성공!` and the browser console showed 0 errors. Other browsers, Android, UEFI, real hardware, OS memory and drivers are unverified.

## M2 unsigned u32 / u64 typed execution proof (new local)

`python3 scripts/test_u32.py` compiles the same source [examples/u32-kernel.html](../examples/u32-kernel.html) to a **native Linux process** and a **real Limine/QEMU BIOS boot ISO**. Exact output tests u32 `4294967295 + 1` wrapping to `0`, explicit `u64(...)` widening yielding `4294967296`, typed function parameters and returns, and the `typed PASS` branch. A changed u32 input yields different expected numeric results and `typed FAIL`, with a wrong-output negative control. Both targets reject u32 literal overflow, mixed-width arithmetic and implicit conversions with filename/line diagnostics. `tests/test_u32.py` also checks unsupported i16 types remain forbidden, u32 operator codegen, scope shadows and legacy u64 compatibility. **Status: LOCAL + GitHub CI + Chromium browser PASS.** Exact-head PR #27 test runs `45041369875` and `45041410553`, merged main CI `45041538665`, and Pages build/deploy `45041538640` succeeded. Connected Chromium/Playwright visited `https://eun-si123.github.io/html-kernel-os/play.html?verify=u32-d2ced5`, selected `u32`, clicked `브라우저에서 부팅하기` and observed actual COM1 text `Native u32 types in HTML Kernel!\n4294967295\n0\n1\n4294967295\n4294967296\ntyped PASS\n` with success status and 0 console errors. Real hardware, UEFI, Android/mobile and other browser engines remain unverified.

## M2 signed integers, bitwise operations, bounded loop exits (local + CI + browser verified)

- Source: [examples/signed-bits-kernel.html](../examples/signed-bits-kernel.html). `python3 scripts/test_signed_bits.py` compiles the **same HTML** into a freestanding x86-64 Limine/QEMU BIOS kernel and a normal Linux executable. Original exact decimal outputs include `-2147483648`, signed i32 wrap to `2147483647`, `-9223372036854775808`, signed i64 wrap to `9223372036854775807`, bitwise value `43`, zero result for a 32-bit overshift and the nearest-loop `break/continue` outputs `1\n3`. Both targets **LOCAL PASS**; QEMU's test exit is 33, while Linux exits 0.
- HTML source mutation changes the minimum i32 literal and the success predicate, generating a **different real ISO** and exact changed Linux/QEMU output (`-2147483647`, `-2147483648`, `typed signed and loop FAIL`). A wrong-output negative control rejects the altered ISO. Invalid signed literal ranges, mixed-width arithmetic, bitwise-on-signed, orphan break and implicit signed/unsigned mixtures fail compilation on **both** targets with filename and line.
- `scripts/test_signed_bits.py` additionally compiles the source at GCC `-O0` and `-O3` with `-Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all` and compares exact stdout and exit code. Both optimizations **LOCAL PASS** with no sanitizer reports.
- Independent `python3 scripts/test_integer_oracle.py` derives **464 deterministic signed/unsigned arithmetic and bitwise expected outputs** from Python's integer arithmetic, then runs the generated Linux C under GCC `-O0` and `-O3` with UBSan. **464/464 match in both builds** locally. This is an arithmetic correctness test, **not a CPU performance benchmark**.
- `tests/test_signed.py`, `tests/test_bitwise.py`, `tests/test_loop_control.py` cover signed extremes, modulo overflows, all four explicit conversions, strict mixed-width rejection, unsigned logical shift bounds, nested loop exits, unreachable statements and escaping lexical scopes. Source parsing/unit tests are separate from native execution.
- **GitHub and public browser PASS:** source implementation PR #29 CI runs `45043311224`, `45043344382` **SUCCESS**; merged main CI `45043441128` **SUCCESS**; GitHub Pages build+deploy `45043441311` **SUCCESS**. The public seventh ISO `https://eun-si123.github.io/html-kernel-os/html-kernel-signed.iso` returned HTTP 200 (4,364,288 bytes). Connected Chromium/Playwright opened `https://eun-si123.github.io/html-kernel-os/play.html?verification=signed-4a60738`, selected `signed` and clicked the boot button. The status was `선택한 HTML 커널의 실제 시리얼 출력 검증 성공!` with actual COM1 output `Typed signed integers and bitwise kernel!\n-2147483648\n2147483647\n1\n2\n-9223372036854775808\n9223372036854775807\n-1\n18446744073709551615\n43\n0\n4294967295\n1\n3\ntyped signed and loop PASS\n`; browser console 0 errors. **NOT VERIFIED:** mobile/other browser engines, UEFI or physical hardware. None of this implements memory allocation, interrupts, disk I/O, drivers or a general-purpose OS.

## P2 Linux userspace target — independent proof

The same compiler front-end accepts the original kernel source and M2 arithmetic source with a Linux output backend. Run the following as an unprivileged x86-64 Linux user:

~~~sh
python3 scripts/test_linux.py
~~~

The test compiles generated C with GCC and executes native Linux binaries. It checks exact stdout and clean exit, reruns a mutated HTML expression with changed branch output, and rejects an unsafe expression. It also checks that Linux output contains **no privileged port or CPU-halt assembly**. This is separate from the QEMU kernel test and does not constitute Linux distribution support.

## What counts as proof

| Claim | Required independently inspectable evidence |
| --- | --- |
| Grammar/parser correctness | Positive and malformed-input tests for exact compiler revision |
| Native compilation | Exact command, compiler, architecture and artifact type |
| Site rendering | Static checks and representative desktop/mobile browser inspection; not simulated kernel proof |
| QEMU boot | Bootable image, pinned bootloader version, exact QEMU invocation, captured console/debugcon bytes and automated pass/fail |
| Real hardware boot | Hardware/firmware details, reproducible local steps, on-device observations, recovery strategy |
| Driver/memory/scheduling support | Implementation, negative-path and regression tests, observed effect under appropriate execution environment |

## Milestone acceptance and language usability

The [ROADMAP.md](ROADMAP.md) IDs M0–M6 define feature gates; actual status lives in [STATUS.md](STATUS.md). [PROJECT_RISKS.md](PROJECT_RISKS.md) distinguishes observed limits from hypotheses. The [LANGUAGE_DESIGN.md](LANGUAGE_DESIGN.md) Python-comparison protocol is **NOT RUN** until a sufficiently complete, runnable language core exists.

## Native performance evidence

Follow [PERFORMANCE.md](PERFORMANCE.md): compare equivalent checked-output native programs against C++ and Rust on the same CPU and compiler optimization level, recording toolchain versions, code size and repeated timing distributions. A `-O2` compiler object passing is **not** speed evidence. QEMU output proves boot functionality only, not native-machine speed. Current performance evidence: **NOT RUN**.

## Critical failure cases

- Invalid nesting, duplicate attributes, unsupported tags, missing required blocks or missing output should fail cleanly.
- Treat input as untrusted; add bounded parsing/resource tests before accepting arbitrary uploaded HTML.
- Do not confuse writing to port `0xE9` with actual hardware display or serial driver support.
- Do not execute a native kernel or firmware flashing on the developer's host just to pass a CI gate.
- A new GitHub Actions workflow passing is not evidence of real kernel execution unless it **actually** boots and verifies the generated artifact.

## Agent/reporting checklist

Report (a) changed files, (b) tests run with outputs, (c) exact commit/PR CI, (d) missing QEMU/physical test, (e) known regressions or safety risks. If a test is unavailable, write NOT RUN rather than PASS.

## M3 native framebuffer verification (opt-in experiment)

```sh
python3 scripts/test_video_console.py # actual Limine RAM, original/mutated source and QEMU pixel readback
python3 scripts/test_video_screen.py # independent QEMU monitor VGA screendump and PNG proof
```

A serial debugcon success is **not** a framebuffer success. `FB_PIXELS_OK` verifies a guest read of a pixel written through the Limine mapped framebuffer; a **separate** QEMU monitor screenshot test verifies actual VGA output RGB at the known header, background and source-generated glyph coordinates. They are distinct evidence classes. CI also runs GCC UBSan host rasterizer/mode/canary tests. Both QEMU checks passed in PR Actions `45096047162` at `9df6e93` (actual PNG packaged in artifacts); the public v86 site and physical PC are still NOT tested with the new ISO. The HTML compiler's hosted GCC flags must explicitly select x86-64 baseline ISA because a native BMI2 `SHLX` caused a real QEMU illegal-instruction exception before this was fixed. The PNG artifact is a verifiable visual reference, not an emulated browser screenshot.

## M3 authentic CPU faults under BIOS QEMU

```sh
python3 -m unittest tests.test_exception_idt -v # host C 16-byte IDT layout and rejects, GCC UBSan -O0/-O3
python3 scripts/test_exception_idt.py       # genuine #DE/#UD/#GP/#PF and normal HTML, map+video composition
```

CI actually boots six source-generated ISOs or more (normal, changed HTML, four distinct CPU fault images, and a combined IDT+memory+framebuffer image). Each intentional fault must emit a deterministic `M3_EXCEPTION V=..` vector, 16-digit saved RIP and error-code field (plus CR2 for #PF), then exit QEMU with **non-success code 45** rather than silently resetting or reaching `kernel_main`. A simulated call to the output function would not meet this evidence gate. The IDT can only **detect and halt**, not recover or resume. No real UEFI/physical machine or v86 browser execution was checked for this opt-in image. The specific evidence baseline is branch GitHub Actions `45096792405` (SUCCESS, before final documentation changes).

## M3 private CR3 map/unmap, fault and restoration gate

```sh
python3 -m unittest tests.test_paging_tables -v # pure GCC UBSan -O0/-O3 table layout and invalid-frame controls
python3 scripts/test_paging_probe.py      # real BIOS QEMU independent normal/modified/invalid alias boots
```

A positive mapping proof requires a genuine CPU virtual-address load/store after writing a private CR3, equality with the Limine HHDM physical address, PTE clearing, TLB invalidation and **successful return to the original CR3** before executing an HTML source-derived kernel. An invalid-mapping proof requires actual CPU #PF after unmap, reported CR2 `FFFFA00000000000` and non-success exit 45, never a fake diagnostic call. The combined source boot must keep the existing physical pool + IDT + native RGB framebuffer working. Branch real QEMU CI `45097571139` and merged-main run `45097936323` passed, but this isolated test is **not** an arbitrary map/unmap, concurrency, recovery, browser or physical-hardware proof.

## M3 controlled CPU page-fault recovery (not general paging)

```sh
python3 -m unittest tests.test_frame_owner -v   # owner allocation/reclaim and exhaustion, GCC UBSan -O0/-O3
python3 scripts/test_paging_recovery.py        # actual CPU #PF, one-shot mapping and iretq retry
```

The positive gate is an **actual page fault followed by reexecution of the original memory load**, verified as zero-fill, then cross-checked through the HHDM physical alias. QEMU must also show deterministic owner reclaim/exhaustion, 16-pages limit and valid source-derived HTML after original CR3 restoration. Negative gate: unarmed wrong-address #PF still prints vector/RIP/CR2 and exits **non-success 45**; wrong CLI flag combos must fail before building. The CPU may set Accessed/Dirty PTE bits after replay: compare address/required flags, not exact raw 64-bit PTE value. The mini-PC Linux/QEMU test passed against branch code at `1b790d2` (before docs). UEFI, browser and real PC NOT RUN for M3 recovery.

## M3 genuine double fault and emergency IST stack gate

```sh
python3 -m unittest tests.test_tss_ist -v  # TSS size and descriptor, GCC UBSan -O0/-O3
python3 scripts/test_tss_ist.py         # genuine #PF on IST2, #DF on IST1, combined boot
```

QEMU builds must actually execute `lgdt`, `lretq`, and `ltr`, confirm original/changed-source HTML, and trigger a **real #DF** by poisoning test-only IST2 and causing a CPU #PF that cannot be delivered. It must observe `M3_IST_DF_STACK_OK`, vector8, and QEMU non-success status 45. A normal page fault independently checks IST2, while a positive integration boot performs one-shot CPU #PF repair on IST2 and finishes real framebuffer rendering. Unrecognized flag combinations are compile-time rejections; no synthetic direct handler invocation qualifies. BIOS QEMU only; **UEFI, browser for this ISO, IRQ hardware, and physical PC NOT RUN**.

## M3 bounded multi-page QEMU acceptance evidence

```sh
python3 -m unittest tests.test_paging_tables -v  # GCC UBSan -O0/-O3 map/unmap constraints
python3 scripts/test_multimap.py                # actual 3x3 CPU aliases, physical frame reuse, revoked #PF
```

The positive path must exercise three additional 4KiB leaf PTEs under a private CR3 for *three rounds*, each read/write confirmed via distinct Limine HHDM physical aliases; safely unmap/invlpg before returning owner-tagged frames and verify deterministic reuse and unchanged first-page mapping. The negative path triggers **real CPU #PF** at `0xFFFFA00000002000` after unmap and requires CR2 match plus fail-stop exit 45. The combined real kernel must prove physical pool, TSS/IST, approved first-page `iretq` fault repair, frame ownership and framebuffer pixel writes. CLI flag rejection and modified HTML source are independent controls. Only bounded BIOS QEMU acceptance is implied: no generic heap, ring3 or external IRQ/hardware claim. Independent mini-PC QEMU test PASS; exact branch push Actions `45105414876`, PR Actions `45105421245`, and PR security `45105418201` all SUCCESS at commit `7bfa7a1`. Post-merge main CI remains separately subject to verification.

## Boot Lab live evidence — browser observation, not synthetic boot animation

```sh
node --check site/play.js
python3 -m unittest tests.test_site -v
```

The UI must receive actual `screen-put-char` VGA BIOS text events, record v86 lifecycle events with measured wall-clock timestamps, and render raw `serial0-output-byte` characters **as they arrive**, regardless of eventual exact-match verification. Selected example HTML comes from a file copied in the same Pages build that compiled its ISO (no inserted fake source). Literal print-line highlighting can be claimed only for matched COM1 text, never for execution of arbitrary expressions, Limine or BIOS. Optional slow mode must use actual v86 `stop/run`; it pauses CPU progress, not changes CPU frequency. Verify the controls separately with a live browser emulator after Pages deployment. See [BOOT_LAB_LIVE_TRACE.md](BOOT_LAB_LIVE_TRACE.md).

## 2026-11-23 Boot Lab live-browser verification result

The deployed build at main `ce833cc9` was checked independently in Chromium after Pages Actions `45110667679` SUCCESS. **Slow actual v86 CPU pacing:** BIOS VGA text 1.99s, first COM1 5.55s, complete source-generated native output 5.56s, glyph RGB `(224,240,228)`, canvas panel 337px, matching source HTML line highlighted, v86 manual pause and resume events, verified replay PASS. **Normal actual v86 run:** M1 `basic` ISO, real SeaBIOS VGA then exact source-generated COM1 by 1.05s PASS; matching HTML source line highlighted. Console errors zero. These are observed wall-clock timestamps from one browser session, not a performance benchmark. The ISO contains *no HTML source*; the HTML shown in the site is copied separately by the Pages workflow. See [BOOT_LAB_LIVE_TRACE.md](BOOT_LAB_LIVE_TRACE.md).

## M4-D post-merge hardening (2026-11-23 local)

The existing native `scripts/test_m4_user_preempt.py` now additionally checks 15 task-specific GPR sentinels from actual ring3 code on every loop, verified by a corrupt-R15 CPU #UD negative (45). It tests wrong active CR3 owner during IRQ (57) and revokes a page-table executable mapping **after B has executed it**, then verifies genuine post-CR3-reload CPL3 instruction #PF error 0x14 with CR2 equal RIP (45). The formerly shared copied-image-outside UD2 target was moved inside each independent image. `tests/test_user_preempt_frame.py` verifies IOPL3, NT and VM bit denial at GCC UBSan -O0/-O3. No real hardware, kernel capability expansion or general user ELF loader follows from these proof gates. [QEMU evidence contract](M4_RING3_PREEMPT.md).

## M4-D1/D2 real CPU user timer preemption and crash survival (2026-11-23 local)

Run scripts/test_m4_user_preempt.py and scripts/test_m4_user_fault_preempt.py with the normal pinned Limine cache and native QEMU q35 CPU qemu64,+x2apic, one vCPU. D1 requires three repeated correct A0 B0 A1 B1 A2 B2 CPL3 IRQ-preempted runs, different HTML source -> different ISO -> different guest debugcon bytes, failure exit 57 for unsupported CPU and forged user CS, and finite timeout proving that masked timer cannot preempt the non-yielding user loop. D2 requires three repeated A #PF (real IST2, error 5) -> reclaim A's six frames -> original B's continued B2 B3 B4 progress -> total frame owner live=0, exact HTML output and QEMU exit 33. Genuine unexpected B #GP must fail-stop exit45 without any successful completion marker. Invalid flag combinations reject. Host tests/test_user_preempt_frame.py uses the runtime-shared frame validator in GCC UBSan -O0/-O3 and rejects malformed saved CPU frames. The verified scope is two trusted fixed user programs on one QEMU CPU only; no proof of general untrusted syscall, loader, SMP, UEFI or physical hardware. [Full evidence](M4_RING3_PREEMPT.md).
