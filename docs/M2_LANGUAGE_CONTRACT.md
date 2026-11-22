# M2 HTML Kernel language — implemented subset (2026-11-23)

**Status:** source-to-native-C for both kernel and unprivileged Linux process. Existing M1/M2 baseline verified by CI, pure user-defined function extension verified locally and in GitHub CI on x86-64 QEMU BIOS and Linux, plus one Chromium browser run. Overall M2 remains **IN PROGRESS**: typed u32/u64/i32/i64 variables and functions, safe fixed-width arithmetic, bitwise unsigned operations, scoped locals, if/else and bounded loops with break/continue work; modules, safe memory APIs, structs, dynamic input and wider diagnostics remain unimplemented. See [STATUS.md](STATUS.md) for current CI evidence.

This is an **HTML-shaped programming language**, not general HTML. Build-time Python parses and validates a small grammar; it never evaluates source expressions as Python code.

## Runnable example

Eight runnable M2 examples are [math-kernel.html](../examples/math-kernel.html), [functions-kernel.html](../examples/functions-kernel.html), [scoped-functions-kernel.html](../examples/scoped-functions-kernel.html), [else-kernel.html](../examples/else-kernel.html), [u32-kernel.html](../examples/u32-kernel.html) [signed-bits-kernel.html](../examples/signed-bits-kernel.html) and [while-kernel.html](../examples/while-kernel.html).

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
- **Numeric output:** `<print value="..."/>` prints unsigned u32/u64 and signed i32/i64 in decimal with a newline, including the full i64 minimum `-9223372036854775808`; literals default to unsigned u64 unless negative, which defaults to signed i64. Combining a value attribute with text is invalid.
- **Variables and scopes:** onboot supports typed `let` and `set` for all four fixed-width integer types. Inside functions, typed u32/u64/i32/i64 `<let>` and `<set>` also work in the body and nested `<if>`/`<else>`/`<repeat>`. An `if` or `repeat` opens a lexical scope; locals disappear when that scope ends. Inner scopes may shadow outer names; `set` updates the nearest visible binding. Redeclaring a name in the same scope, accessing an out-of-scope name, or reading an undeclared variable fails at compile time. Parameters start in function scope.
- **Integer expressions:** supported exact-width types are unsigned `u32`, `u64` and signed `i32`, `i64` with normal two's-complement signed ranges. Addition, subtraction, multiplication and unary signed minus **wrap modulo 2^width**, then interpret the resulting bit pattern using the declared signedness. The compiler emits **unsigned intermediate operations plus range-safe signed conversion helpers**, avoiding C signed-overflow undefined behavior. Literal-only expressions adopt an expected declared/parameter/return type; a standalone positive numeric print defaults to u64, a standalone negative one to i64. Out-of-range typed literals fail compilation.
- **Conversions:** different integer widths and signedness cannot mix implicitly, even for comparison/assignment/function calls. Explicit `u32(x)`, `u64(x)`, `i32(x)`, `i64(x)` conversions accept one integer expression and keep the low target-width bits; signed targets interpret that bit pattern in two's complement. Converting negative signed values to unsigned follows modulo-2^width, and same-width unsigned-to-signed conversion uses defined arithmetic rather than out-of-range C casts.
- **Bitwise operations:** `&`, `|`, `^`, unary `~`, `<<`, `>>` are supported **only for u32/u64**; signed operands must explicitly convert. In HTML attributes, escape operators as `&amp;`, `&lt;&lt;` and `&gt;&gt;`. Shifts are logical; shift counts at least the operand width return zero rather than invoking undefined C shift behavior. Boolean `and`/`or`/`not` remain separate from bitwise operations.
- **Still unsupported:** division/modulo, shifts on signed operands, array/index access, arbitrary C/Python expressions, dynamic loops and unrestricted calls. Only the validated typed function and numeric conversion call forms are accepted.
- **Conditional / else:** `<if test="score &gt; 10">...<else>...</else></if>` tests a comparison. `else` is optional, must be the **final direct child** of `if`, may occur only once and cannot have attributes. When the condition is false, only the else branch executes. Nested `if/else` is supported in onboot and typed functions. Comparisons `==`, `!=`, `<`, `<=`, `>`, `>=` and boolean `and`/`or`/`not` are accepted; in attributes use `&lt;`/`&gt;` for angles. A branch in a function creates its own lexical scope; declarations do not leak between branches. A `return` can be the final statement of either branch, but a final unconditional function return is still required.
- **Repeat/break/continue:** a literal decimal times count from 0 to 64. Nesting is bounded. `<break/>` exits the nearest enclosing repeat and `<continue/>` skips the remainder of the current iteration; both are legal inside nested if/else only when a repeat surrounds them. They reject orphan placement and statements unreachable after them in the same function block. Within `onboot`, repeats can print, set and use nested control flow. Functions additionally support lexical locals and early returns. The static work/output budget stays conservative even for early exits.
- **Bounded conditional while (M2 extension):** `<while test="n &lt; 3" max="5">...</while>` evaluates a boolean condition before each iteration and performs at most the integer literal `max` iterations (0..64), regardless of whether the condition remains true. The guard is checked only while iteration capacity remains. The condition may read variables and call typed pure functions; guard checks and function calls count toward worst-case work budgets. `break` and `continue` target the nearest enclosing `repeat` or `while`. In functions, loop bodies create lexical scopes, so inner bindings do not escape. No unbounded `while` syntax is allowed. Native Linux/QEMU evidence for this extension must come from CI, not from this document.
- **Typed functions:** `<function name="double" params="x:u64" returns="u64"><return value="x * 2"/></function>` remains valid as a sibling of `<onboot>`. A function body may now contain typed local declarations, assignment, nested bounded repetition and conditional branches plus numeric returns. A final unconditional top-level `<return value="..."/>` is **mandatory**; additional early returns may appear as final statements in nested `if`, `else` or `repeat` blocks. Statements following a return in the same block are rejected as unreachable. This conservative rule avoids missing returns on a false branch or zero-trip loop. Functions remain externally side-effect-free: no `<print>`, hardware access, mutable global state or arbitrary runtime calls inside them.
- **Function limits:** at most 32 functions, 4 typed u32/u64/i32/i64 positional parameters, all four integer return types, maximum call-chain depth 8, no direct/indirect recursion. Expanded function work counts toward the 20,000-step program limit. Invalid signatures, arities, unknown functions and non-number arguments are rejected.
- **Halt:** optional final top-level halt; no statements may follow it.
- **Identifiers:** ASCII letters or underscore followed by letters, digits or underscores; Python keywords are disallowed.
- **Limits:** source at most 128 KiB, 1024 elements, 16 nesting levels; text prints at most 4096 bytes; expressions at most 256 UTF-8 bytes and 64 AST nodes; estimated output at most 16 KiB and execution at most 20,000 statement steps.
- **Diagnostics:** unsupported syntax, bad nesting or attributes (including invalid else position/duplication), duplicate/undefined variables and unbounded constructs cause compilation to fail. Most semantic errors include source line and column; the CLI also prints the input filename for compilation errors.

## Reproducible verification

~~~sh
python3 -m unittest discover -s tests -q
python3 scripts/test_boot.py
python3 scripts/test_language_boot.py
python3 scripts/test_functions.py
python3 scripts/test_scoped_functions.py
python3 scripts/test_else.py
python3 scripts/test_u32.py
python3 scripts/test_signed_bits.py
python3 scripts/test_while.py
python3 scripts/test_integer_oracle.py
python3 scripts/build_boot.py --source examples/math-kernel.html --out build/html-kernel-math.iso
~~~

The arithmetic test runs QEMU for original/changed expressions; `test_functions.py` covers typed pure functions; `test_scoped_functions.py` compiles the same scoped program for native Linux and QEMU and verifies both altered and baseline outputs, missing return/scope errors, and wrong output rejection. GitHub PR #23 and merged main CI both passed; public Pages now deploys **seven** independent bootable ISOs; the signed/bitwise/loop-control demo was also booted in connected Chromium and verified through actual COM1; scoped functions, if/else branches and u32/u64 arithmetic have been booted in connected Chromium and verified through actual COM1. The if/else PR #25 CI run `45039571823`, main CI `45039645315` and Pages run `45039645280` all passed. The u32/u64 feature PR #27 CI runs `45041369875` and `45041410553`, merged main CI `45041538665`, and Pages deploy `45041538640` all passed; the u32 ISO booted in connected Chromium with exact expected COM1 output. Signed/bitwise/loop-control PR #29 CI `45043311224` and `45043344382`, merged main CI `45043441128`, Pages build/deploy `45043441311` all succeeded. Chromium successfully booted the seventh ISO and received exact signed, bitwise and bounded-loop COM1 output. Other browsers/mobile/physical hardware remain unverified.

## Shared Linux process proof (P2)

The same compiler emits a Linux userspace C program using a different output adapter, reusing the exact AST and expression semantics without root access or direct hardware ports:

~~~sh
python3 compiler/htmlk.py examples/math-kernel.html --target linux --out build/math-linux.c
gcc -std=c11 -O2 -Wall -Wextra -Werror build/math-linux.c -o build/math-linux
./build/math-linux
python3 scripts/test_linux.py
~~~

Outputs and branch results match the native QEMU kernel. On Linux the halt statement means *normal process exit*, not a CPU halt. Linux distribution or broad POSIX API support is not claimed.

## Limitations

This is not a full language or operating system. Function-local mutable variables are implemented, but recursion, unbounded loops, arrays/structs, I/O inside functions, modules, memory management, user programs, file I/O, physical hardware support and comprehensive performance comparisons are **not implemented/verified**. Browser execution is an independent compatibility test, not automatically proven by QEMU.
