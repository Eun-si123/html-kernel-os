# HTML Kernel OS — code map

Locate the smallest source and test surface. This is a navigation index, **not evidence of implemented functionality**.

| Question | Source of truth | Verification / review |
| --- | --- | --- |
| What is released, planned, or blocked? | [docs/STATUS.md](docs/STATUS.md) | [docs/VALIDATION.md](docs/VALIDATION.md), live CI |
| Which milestone should a human/agent do next? | [docs/ROADMAP.md](docs/ROADMAP.md) | `python3 scripts/roadmap.py --json` (plan only); live Status/Issues |
| How easy can the HTML dialect become? | [docs/LANGUAGE_DESIGN.md](docs/LANGUAGE_DESIGN.md) | grammar, examples, usability studies not yet run |
| How is native execution speed evaluated? | [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | no benchmarks yet; compile `-O2`, compare matched native workloads at M2+ |
| What may break or invalidate a claim? | [docs/PROJECT_RISKS.md](docs/PROJECT_RISKS.md) | risk IDs and disconfirming tests |
| What is the compiler grammar? | [compiler/language.py](compiler/language.py), [compiler/numeric_types.py](compiler/numeric_types.py), [compiler/function_codegen.py](compiler/function_codegen.py), [compiler/htmlk.py](compiler/htmlk.py) | [tests/test_compiler.py](tests/test_compiler.py), [tests/test_language.py](tests/test_language.py), [tests/test_functions.py](tests/test_functions.py), [tests/test_else.py](tests/test_else.py), [tests/test_u32.py](tests/test_u32.py), [tests/test_signed.py](tests/test_signed.py), [tests/test_bitwise.py](tests/test_bitwise.py), [tests/test_loop_control.py](tests/test_loop_control.py), [docs/M2_LANGUAGE_CONTRACT.md](docs/M2_LANGUAGE_CONTRACT.md) |
| What example is accepted? | [examples/kernel.html](examples/kernel.html), [examples/math-kernel.html](examples/math-kernel.html), [examples/else-kernel.html](examples/else-kernel.html), [examples/u32-kernel.html](examples/u32-kernel.html), [examples/signed-bits-kernel.html](examples/signed-bits-kernel.html) | Actual kernel QEMU and Linux userspace proofs |
| Where does the generated C come from? | [compiler/htmlk.py](compiler/htmlk.py) | `build/kernel.c` generated, not committed |
| Is it actually bootable? | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/STATUS.md](docs/STATUS.md) | QEMU BIOS boot verified; see [scripts/test_boot.py](scripts/test_boot.py) and [scripts/test_language_boot.py](scripts/test_language_boot.py) |
| How does the M3 opt-in physical memory bootstrap work? | [boot/page_pool.c](boot/page_pool.c), [boot/memory_probe.c](boot/memory_probe.c), [boot/kernel_entry.c](boot/kernel_entry.c) | [docs/M3_MEMORY_BOOTSTRAP.md](docs/M3_MEMORY_BOOTSTRAP.md), [scripts/test_m3_memory.py](scripts/test_m3_memory.py), host C test + QEMU BIOS | 
| How does the actual guest screen get kernel text? | [boot/console_fb.c](boot/console_fb.c), [boot/kernel_entry.c](boot/kernel_entry.c), [scripts/build_boot.py](scripts/build_boot.py) | [docs/M3_FRAMEBUFFER_CONSOLE.md](docs/M3_FRAMEBUFFER_CONSOLE.md), [tests/test_video_console.py](tests/test_video_console.py), [scripts/test_video_console.py](scripts/test_video_console.py) and actual VGA screenshot oracle | 
| How do actual CPU faults become diagnostics instead of triple faults? | [boot/exception_idt.c](boot/exception_idt.c), [boot/exception_idt.h](boot/exception_idt.h), [boot/kernel_entry.c](boot/kernel_entry.c) | [docs/M3_EXCEPTION_IDT.md](docs/M3_EXCEPTION_IDT.md), [tests/test_exception_idt.py](tests/test_exception_idt.py), [scripts/test_exception_idt.py](scripts/test_exception_idt.py) real QEMU #DE/#UD/#GP/#PF |
| How do private CR3 virtual map/unmap and real page-fault tests work? | [boot/paging_probe.c](boot/paging_probe.c), [boot/paging_tables.c](boot/paging_tables.c), [boot/paging_probe.h](boot/paging_probe.h) | [docs/M3_PRIVATE_PAGING.md](docs/M3_PRIVATE_PAGING.md), [tests/test_paging_tables.py](tests/test_paging_tables.py), [scripts/test_paging_probe.py](scripts/test_paging_probe.py) real BIOS QEMU |
| How does one approved CPU page fault recover and recycle owned physical frames? | [boot/frame_owner.c](boot/frame_owner.c), [boot/paging_probe.c](boot/paging_probe.c), [boot/exception_idt.c](boot/exception_idt.c) | [docs/M3_FAULT_RECOVERY.md](docs/M3_FAULT_RECOVERY.md), [tests/test_frame_owner.py](tests/test_frame_owner.py), [scripts/test_paging_recovery.py](scripts/test_paging_recovery.py) genuine #PF and iretq under BIOS QEMU |
| Where are TSS, #DF emergency IST1, #PF IST2 and CPU double-fault evidence? | [boot/tss_ist.c](boot/tss_ist.c), [boot/tss_ist.h](boot/tss_ist.h), [boot/exception_idt.c](boot/exception_idt.c), [boot/kernel_entry.c](boot/kernel_entry.c) | [docs/M3_TSS_IST.md](docs/M3_TSS_IST.md), [tests/test_tss_ist.py](tests/test_tss_ist.py), [scripts/test_tss_ist.py](scripts/test_tss_ist.py) QEMU true #DF/#PF and combined recovery |
| Where is the static site? | [site/index.html](site/index.html), [site/play.html](site/play.html), [site/styles.css](site/styles.css), [site/play.css](site/play.css), [site/app.js](site/app.js) | [docs/WEBSITE_DESIGN.md](docs/WEBSITE_DESIGN.md), [tests/test_site.py](tests/test_site.py), real browser visual and boot checks |
| What does CI verify? | [.github/workflows/ci.yml](.github/workflows/ci.yml) | Exact GitHub Actions run |
| Which regressions map to changed source? | [agent-evals/feature-contracts.json](agent-evals/feature-contracts.json) | `python3 scripts/agent_feature_map.py impact ...` |
| What should agents read first? | [AGENTS.md](AGENTS.md), [docs/README.md](docs/README.md) | Routing / docs-link check |
| Who owns status / open decisions? | [docs/STATUS.md](docs/STATUS.md), [docs/DECISIONS.md](docs/DECISIONS.md) | Source and current GitHub state |

## Boundaries worth keeping separate

- `site/`: static web UI, **not** kernel runtime or a web compiler.
- `compiler/`: build-time parser and code generator, currently Python-based.
- `examples/`: examples for language syntax, not hardware acceptance evidence.
- `tests/`: source/unit/static regression checks.
- `agent-evals/`: advisory mapping of source paths to existing tests; never a release gate by itself.
- `docs/`: status, evidence standards, architecture, decisions, and agent navigation.

Do not introduce a long-running agent service, database, or synthetic feature count simply because another larger repository has one.
