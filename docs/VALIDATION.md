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
