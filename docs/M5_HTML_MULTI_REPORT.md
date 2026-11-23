# M5-F3 — bounded repeated HTML user reports under a real Ring 3 syscall budget

**Status:** local native BIOS QEMU/host source tests PASS. CI and merge must be verified at the exact new PR head. This extends trusted build-time M5-F1/F2 user programs; it is not a general-purpose user-space driver or safe arbitrary-code sandbox.

## One-command interactive proof

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-multireport.html
# Native QEMU COM1: run /apps/hello.hke; help; exit
python3 scripts/test_m5_html_multi_report.py
python3 -m unittest tests.test_html_user_multi_report -v
```

One program can now emit **up to eight** bounded `INT 0x80` ID 2 numeric or ID 3 printable ASCII results, including output from capped `<repeat>` and `<while>` bodies or either `<if>` branch. The HTML parser, typed expressions, loop bounds, checked arrays, readonly user text pointer and COM1 interface are all reused. The source must end with an unconditional top-level `<print value="..."/>` or `<print>ASCII</print>` immediately before `<halt/>`. Other output statements can precede it or occur in nested control flow. The compiler counts a **worst-case report budget**: multiplying by loop iteration maxima and choosing the more expensive conditional branch; more than eight *potential* outputs fails **before any executable/ISO artifact is created**. This is deliberately stricter than dynamic path profiling.

**Crucially, the kernel independently enforces the same bound:** only in `--user-app-html` mode, each genuine user task receives a fresh `user_report_count` on entry and can make at most eight successful report syscalls. A crafted but correctly formed HKEX binary that sends a **ninth** report is terminated using the existing M5-E1 invalid-syscall path; its six owned frames are reclaimed and the real UART shell remains responsive. This is a syscall-count bound, not a calibrated wall-clock quota; the separate M5-E2 x2APIC CPU budget is also enabled by the recommended runner. All legacy assembly/standalone M4/M5 probes keep their earlier single-report semantics; default kernel and browser demo are untouched.

## Actual CPU and source evidence

`python3 scripts/test_m5_html_multi_report.py`: three real BIOS QEMU boots. Each guest runs an HTML program with `<repeat times="2"><print>tick</print></repeat>` and a final unsigned numeric `<print value="2026"/>` **twice**, so each boot emits four actual UART `tick` lines and two real CPL3 2026 results. Between them, an independent hand-assembled Ring 3 `bad-report-budget.hke` delivers **eight accepted numeric 777 results** and then intentionally attempts a ninth; the kernel emits `M5_ERR_USER_SYSCALL`, reclaims exactly that task's six frames, and later executes the healthy HTML program. Another nonyielding Ring3 task is truly interrupted by x2APIC, after which the original HTML kernel executes and guest exits successfully. Changing only user source `tick→tock` and `2026→2027` creates a different ISO and exact changed native COM1 output; changing only the kernel HTML changes the final kernel output. A 9-output HTML program fails its compiler budget with no ISO.

Host `tests/test_html_user_multi_report.py` checks strict unsigned/string limits, if/else/while expansion, final unconditional output, static 8-call acceptance/9-call rejection and no privileged OUTB in the user target. F2's `boot/user_text_policy.c` continues validating every actual text pointer and byte; user programs cannot send arbitrary kernel addresses or terminal control sequences.

## Explicit limits

Trusted build-time app source, up to eight bounded reports per task, max one user RO code page and one stack page, one running app at a time, no dynamic printf, Unicode text, terminal control characters, arbitrary pointer copyin/copyout or multitasking service. An infinitely looping handcrafted user program still needs x2APIC timeout recovery (only proven under the exact QEMU single-vCPU profile). No physical PC, UEFI, writable disk, SMP or untrusted-code security certification. Use [M5-F1](M5_HTML_USER_PROGRAM.md) and [M5-F2](M5_HTML_USER_TEXT.md) for earlier gates.
