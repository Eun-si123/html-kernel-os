# M5-F5 — full unsigned 64-bit native HTML user reports

**Scope:** opt-in trusted build-time HTML → C → ELF → HKEX → actual x86-64 CPL3 user mode in BIOS QEMU. Local guest and host checks PASS. PR #93 exact-head QEMU Actions `45144365569`/`45144419904` and Gitleaks `45144420245` PASS; merged `b88c182`. This is not a general-purpose application security boundary.

## Before/after: a concrete type/ABI mismatch

The shared HTML language already supported `u64` arithmetic and `<print value="..."/>` in a user program. But the kernel's existing ID-2 `INT 0x80` report handler accepted RDI **only through 9999**, and its private decimal formatter used a five-character buffer and 32-bit argument. Consequently an otherwise valid HTML user program printing `10000`, `4294967296`, or the type's maximum `18446744073709551615` was killed as an invalid syscall. This was a contract mismatch rather than a parse failure.

The opt-in M5-F5 build defines `HTMLK_M5_USER_U64_OUTPUT` **only for `--user-app-html`**, preserving the strict legacy M4/M5-C1 and assembly-only numeric report bound. In that mode, syscall ID 2 accepts the complete 0..2^64−1 RDI register range. The freestanding kernel decimal formatter now uses a 20-byte private stack buffer with real unsigned 64-bit division and no dynamic heap or format-string parser. This is architectural x86-64 code in the native kernel, not browser-side string conversion. Existing output prefix `M5_C_USER_VALUE=` and actual UART/E9 outputs are unchanged.

## Run it

Source `examples/user-programs/html-u64-report.html`:

```html
<kernel arch="x86_64"><onboot>
  <repeat times="2"><print value="4294967296"/></repeat>
  <print value="18446744073709551615"/>
  <halt code="7"/>
</onboot></kernel>
```

```sh
python3 scripts/run_m5_console.py --html-user-app examples/user-programs/html-u64-report.html
# At native COM1 prompt: run /apps/hello.hke
# M5_C_USER_VALUE=4294967296 (twice)
# M5_C_USER_VALUE=18446744073709551615
# M5_RUN_EXIT_CODE=7
# At COM1 prompt: exit
python3 scripts/test_m5_html_u64_output.py
python3 -m unittest tests.test_html_user_u64_output -v
```

The exit status is the separate M5-F4 guarded process result, emitted only after the six frames have been reclaimed. The number of `print` syscalls per HTML program remains **strictly capped at eight** by both the shared compiler's worst-case estimate and an independent counter in the real Ring3 syscall dispatcher; allowing a larger numeric *value* never allows a ninth *report*. User text output remains separately limited to validated printable ASCII and known user RO-page pointers.

## Genuine native proof and negatives

`scripts/test_m5_html_u64_output.py` builds an ISO from the actual HTML source and repeats three full BIOS QEMU x2APIC boots. In each boot, a native user app reports `4294967296` twice and `18446744073709551615` once, exits with status 7, then a distinct hand-assembled CPL3 app successfully reports 10000 in the HTML-enabled mode. Another hand-assembled program makes **eight accepted numeric syscall reports** and is terminated on its ninth. An independent nonyielding user app is stopped by the **actual x2APIC IRQ**; the original healthy HTML-compiled app runs again and the kernel exits with true HTML-derived native output. The test asserts the real debugcon **and** COM1 serial bytes, exact user cleanup and error classification, and no forged-success markers.

Additional independent acceptance: change only the HTML literals (2^32→2^32+1, UINT64_MAX→UINT64_MAX−1) and compare **different ISO bytes and different CPU/UART output**; run an eight-report HTML program where **every** output is `18446744073709551615`; reject a source literal above UINT64_MAX before creating an ISO; and prove a standalone **legacy M5-C1** executable reporting 10000 still fails closed (QEMU exit 53) instead of silently inheriting the new ABI. `tests/test_html_user_u64_output.py` checks 0, 9999, 10000, 2^32 boundaries, UINT64_MAX, compiler overflows, signed report denial, old kernel/Linux compilation and the 8-call source limit.

## Deliberate limits

Only unsigned u32/u64 numeric results; signed i32/i64 user outputs were not supported in F5; see the separate [M5-F6 extension](M5_HTML_I64_OUTPUT.md). Typed HTML programs, known compile-time images, one program at a time, read-only ROMFS and a bounded 4KiB user image. No generic printf, formatting options, user-space file I/O, network, arguments/env, random untrusted binaries, SMP/XSAVE/FS/GS, calibrated wall-clock budget or physical PC compatibility. FNV in the HKEX header checks corruption, not authenticity. Full M5-E3 production robustness and M6 real-hardware trials remain OPEN.
