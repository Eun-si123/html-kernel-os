# Engineering risks and assumptions — HTML Kernel OS

This is a **risk register, not a report of observed defects**. Labels: **CONFIRMED LIMITATION** = visible in current source/toolchain; **NEEDS VERIFICATION** = design or future integration may fail; **HYPOTHESIS** = plausible concern without demonstrated failure. Entries are risks to investigate, **not probability estimates or verified defect reports**.

| ID | Risk and evidence type | Potential impact | Concrete mitigation / distinguishing test | Gate |
| --- | --- | --- | --- | --- |
| **R1** | **CONFIRMED LIMITATION:** object compilation does not provide a boot entry/bootloader | No OS can boot | Build pinned boot protocol + headless QEMU test; assert HTML-derived output and bounded termination | M1 |
| **R2** | **NEEDS VERIFICATION:** stdlib HTMLParser may accept or normalize syntax outside the intended strict language | Compiler accepts malformed code or silently changes meaning | Dedicated syntax fixtures, precise AST diagnostics, malformed tag/attribute tests, input caps; consider a stricter tokenizer | M2 |
| **R3** | **NEEDS VERIFICATION:** easy markup does not guarantee readable real programs or safe low-level access | Unsafe memory operations / unwieldy language | Type/effect contract, privileged operations, five-task comparison with Python, novice testing | M2–M3 |
| **R4** | **NEEDS VERIFICATION:** bootloader/CPU ABI, linker, debugcon and environment drift | Boot failure or misleading CI | Pin Limine/QEMU/toolchains; verify linker symbols, output source and machine options; negative boot test | M1 |
| **R5** | **NEEDS VERIFICATION:** malicious/huge input to compiler | Hang, memory exhaustion, unintended file access | Limit bytes/depth/expansion; reject unsupported syntax; run compiler under bounded subprocess in CI | M2 |
| **R6** | **NEEDS VERIFICATION:** memory map and interrupt misuse | Kernel crash / privilege corruption | Reserved-region tests, invalid mapping traps, panic-path visibility, fault injection in QEMU | M3–M4 |
| **R7** | **CONFIRMED LIMITATION:** GitHub Pages only serves static website content | Site mistaken for a native OS demo | Explicit website labels; separate browser preview from native/QEMU test; independent deployment permission | All |
| **R8** | **NEEDS VERIFICATION:** external artifacts and build tool versions change | Non-reproducible or compromised builds | Pin/check upstream boot assets and tool versions, least-privilege CI, inspect licenses | M1–M6 |
| **R9** | **NEEDS VERIFICATION:** premature real-PC experimentation | Data loss, unusable boot path, host damage | No production disk writes or firmware flashing; disposable QEMU then spare hardware, recovery media, explicit field approval | M6 |
| **R10** | **CONFIRMED LIMITATION:** no OSS license selected | Outside contributors lack clear reuse permissions | Choose license with owner before accepting derivative contribution or implying Open Source license grants | Governance |

## Assumptions to falsify early

- Compiling HTML-derived C with `-ffreestanding` does **not** guarantee the object follows a boot ABI. **Test:** actual QEMU handoff.
- QEMU debugcon port `0xE9` is a debug channel, not generic hardware display. **Test:** compare configured QEMU output to a physical device without assuming identical I/O support.
- Browser DOM parsing is a poor authority for kernel language semantics until the grammar is explicitly fixed. **Test:** feed malformed, auto-closable, nested, entity-heavy and mixed-case input.
- A second compiler/runtime abstraction is justified only when it reduces observed complexity or enables necessary native semantics. **Test:** baseline implementation + counterexample before adopting new dependencies.
- Tiny HTML demos might be easy, while realistic kernel code becomes verbose. **Test:** five-task language usability benchmark, not intuition.
- Agent-generated plans, implementation, tests, emulator runs and physical tests are independent evidence classes. **Test:** compare exact produced artifacts and logs with stated milestone gate.

## Operational actions

For every risk-sensitive PR: identify the relevant R-ID, add one failure scenario or explain why not runnable, cite exact source/CI, and update [STATUS.md](STATUS.md) *only* after evidence. Keep the risk separate from an actual bug; record confirmed defects in GitHub Issues.

[ROADMAP.md](ROADMAP.md) owns future gates; [VALIDATION.md](VALIDATION.md) owns proof classes; [DECISIONS.md](DECISIONS.md) owns undecided design choices.
