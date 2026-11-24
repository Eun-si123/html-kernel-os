# M5-F6 — signed native HTMLK user numeric reports

**Development branch; local QEMU evidence, not a full M5 security gate.**

The shared language previously supported signed i32/i64 output on the
Linux and kernel targets but rejected the same valid expressions on
the Ring3 target. This extension uses a separate register-only syscall
ID 4, enabled only with the existing HTML source/proof opt-in builder.
ID 2 retains its unsigned meaning, including UINT64_MAX. Legacy
assembly-only modes deny ID 4. All text and numeric reports still
share a single eight-report per-process limit; no extra pointer or
memory permission is introduced. The compiler sign-extends i32 through
int64_t before conversion to uint64_t. The kernel handles the sign bit
and computes negative magnitude in unsigned arithmetic, including INT64_MIN,
without an overflowing signed negation or implementation-defined cast.

```sh
python3 scripts/test_m5_html_i64_output.py
python3 scripts/htmlk.py run examples/user-programs/html-i64-report.html
```

Actual native CPU output: -2147483648, -7, -9223372036854775808,
9223372036854775807, 0, 18446744073709551615. Three real QEMU boots
each check two healthy runs, mixed signed/unsigned eight accepted reports
and ninth rejection, independent x2APIC timeout and page reclamation.
A changed source changes ISO bytes and actual output (-7 to -9);
legacy ID 4 is denied. The existing unsigned output marker is preserved
with signed decimal text for signed reports. This ABI is still a
build-wide opt-in for trusted ROMFS, not per-image authorization or
an arbitrary-code security boundary. Browser/hardware and exact CI
remain separate evidence gates.
