# M2 HTML Kernel language — implemented subset (2026-11-22)

**Status:** source-to-freestanding-C implementation verified by a local x86-64 QEMU BIOS boot. Overall M2 remains **IN PROGRESS** because functions, more types and broader diagnostics are not implemented. See [STATUS.md](STATUS.md) for current CI evidence.

This is an **HTML-shaped programming language**, not general HTML. Build-time Python parses and validates a small grammar; it never evaluates source expressions as Python code.

## Runnable example

The complete file is [examples/math-kernel.html](../examples/math-kernel.html).

~~~html
<kernel arch="x86_64">
  <onboot>
    <let name="score" type="u64" value="2 + 3 * 4"/>
    <repeat times="3">
      <print value="score"/>
      <set name="score" value="score + 2"/>
    </repeat>
    <if test="score == 20"><print>condition PASS</print></if>
    <halt/>
  </onboot>
</kernel>
~~~

The example prints 14, 16, 18 and "condition PASS" in actual QEMU boot. The full fixture also prints unsigned wraparound 0 minus 1 as 18446744073709551615.

## Implemented contracts (first slice)

- **Root:** one kernel element with optional arch=x86_64 attribute and exactly one onboot.
- **Text:** print literal UTF-8 content emits a newline to QEMU debugcon and COM1.
- **Numeric output:** print with value attribute emits a unsigned decimal number and newline; combining the value attribute with text is invalid.
- **Variables:** let with name, type=u64 and value declares a top-level onboot variable; set with name and value reassigns. Declare before use and do not redeclare. Declarations inside loops/branches are not supported.
- **Numeric expressions:** 0 through 2^64-1 integer literals, previously declared variable names, parentheses and +, -, *. Arithmetic is **unsigned modulo 2^64**. Division, shifts, signed numbers, calls, indexing and arbitrary C/Python expressions are rejected.
- **Conditional:** if with test attribute accepts ==, !=, <, <=, >, >= comparisons and boolean and/or/not. Within HTML attributes use &lt; / &gt; for the angle-bracket operators. No else statement yet.
- **Repeat:** a literal decimal times count from 0 to 64. Nesting is accepted but conservatively bounded. The body can print, set or contain nested conditional/repeat tags.
- **Halt:** optional final top-level halt; no statements may follow it.
- **Identifiers:** ASCII letters or underscore followed by letters, digits or underscores; Python keywords are disallowed.
- **Limits:** source at most 128 KiB, 1024 elements, 16 nesting levels; text prints at most 4096 bytes; expressions at most 256 UTF-8 bytes and 64 AST nodes; estimated output at most 16 KiB and execution at most 20,000 statement steps.
- **Diagnostics:** unsupported syntax, bad nesting or attributes, duplicate/undefined variables and unbounded constructs cause compilation to fail. Most errors include source line and column.

## Reproducible verification

~~~sh
python3 -m unittest discover -s tests -q
python3 scripts/test_boot.py
python3 scripts/test_language_boot.py
python3 scripts/build_boot.py --source examples/math-kernel.html --out build/html-kernel-math.iso
~~~

The language boot test launches QEMU for the example and for a changed source expression, checks the expected branch outcome and rejects deliberately wrong output and invalid source. GitHub Actions will perform the same tests; Pages will provide separate ISO files for the basic boot and arithmetic demos.

## Limitations

This is not a full language or operating system. Functions, signed types, input, memory management, user programs, file I/O, physical hardware support and comprehensive performance comparisons are **not implemented/verified**. Browser execution is an independent compatibility test, not automatically proven by QEMU.
