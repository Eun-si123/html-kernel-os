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
