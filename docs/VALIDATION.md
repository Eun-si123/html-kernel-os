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

Run `python3 scripts/test_else.py`: it compiles one HTML fixture into a real Limine x86-64 kernel image and a normal Linux binary, executes both, checks exactly the same serial/stdout bytes (baseline includes else branch, true/false function branches, nested if/else and bounded repetition), then mutates the else-side value (`8` to `9`) and confirms changed native output plus ISO provenance. Wrong-output expectations and orphan/duplicate else and leaked variable references are rejected in both targets. `tests/test_else.py` covers parser nesting, lexical scopes, output/work budgets, early returns and compiler CLI file+line diagnostics. Current result: **local QEMU + Linux PASS; independent PR CI and published browser demo pending**. This does not prove new OS memory or driver support.

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
