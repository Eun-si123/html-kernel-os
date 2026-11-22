# HTML Kernel language design — readable syntax, explicit systems semantics

**Status: design discussion, not a finished language specification.**
The **implemented subset** lives in [compiler/language.py](../compiler/language.py), [compiler/htmlk.py](../compiler/htmlk.py) and [M2_LANGUAGE_CONTRACT.md](M2_LANGUAGE_CONTRACT.md). Other examples and general-purpose features remain proposals, not shipped behavior.

## 한국어 핵심

표준 HTML은 Python처럼 함수·변수·반복문을 실행하는 범용 프로그래밍 언어가 아니야. 이 프로젝트는 HTML **태그 문법을 빌린 새로운 네이티브 시스템 언어**를 만드는 실험이야.

- `<print>Hello!</print>`은 Python의 `print("Hello!")`처럼 쉽게 배울 수 있어.
- 하지만 매번 태그를 열고 닫아야 하므로 복잡한 코드에서 Python보다 **읽기 어렵고 길어질 위험**이 있어.
- 커널 구현은 메모리, 인터럽트, 동시성, 권한과 같은 어려운 개념을 필요로 해. **문법이 쉽다고 OS 개발도 쉬워지는 건 아니야.**
- 목표는 **"Python-like ergonomics for common tasks, with explicit safe/unsafe low-level controls"**이지 Python 호환성이나 Python 런타임 채택이 아니야.
- **추가 성능 목표:** 런타임에 브라우저·Python 인터프리터 없이 최적화된 네이티브 코드로 실행해 C++/Rust와 비슷한 속도를 지향해. **현재 비교 측정은 수행하지 않았어.** 검증 방식은 [PERFORMANCE.md](PERFORMANCE.md) 참조.

## The syntax trade-off

| Task | Python (already works) | HTML Kernel dialect |
| --- | --- | --- |
| Print | `print("Hello!")` | `<print>Hello!</print>` **implemented** (debugcon output in native C) |
| Variable | `count = 3` | **implemented, unsigned:** `<let name="count" type="u64" value="3"/>` |
| Repeat | `for i in range(3): ...` | **implemented, bounded:** `<repeat times="3">...</repeat>` |
| Condition | `if count > 0: ...` | **implemented, comparison only:** `<if test="count &gt; 0">...</if>` |
| Function | `def double(x): return x*2` | **implemented (typed u64, scoped blocks):** `<function name="double" params="x:u64" returns="u64"><return value="x * 2"/></function>`; `let`, `set`, `if`, `repeat` inside functions also supported |

### Current working program

```html
<kernel arch="x86_64">
  <onboot>
    <print>Hello from HTML Kernel!</print>
    <halt/>
  </onboot>
</kernel>
```

This example compiles to a real Limine bootable image and runs under QEMU and a tested Chromium browser. An additional numeric expression/loop example is already runnable; see [M2 language contract](M2_LANGUAGE_CONTRACT.md).

### Executable M2 subset: beginner-friendly example

```html
<!-- Supported M2 subset: u64 variable and bounded repeat -->
<kernel arch="x86_64">
  <onboot>
    <let name="count" type="u64" value="3"/>
    <repeat times="3">
      <print>Hello!</print>
    </repeat>
    <halt/>
  </onboot>
</kernel>
```

The first M2 slice uses typed expressions in quoted attributes. This remains a deliberately small subset, not a final language standard. Expression strings inside attributes (e.g., `value="x + 1"`) create a **second embedded language** and introduce quoting/debugging tradeoffs. The implementation restricts the expression grammar and errors explicitly; future alternatives should be compared using real beginner tasks.

## Design principles to review before M2

1. **Strict syntax, no HTML auto-repair:** bad nesting, unknown tags, duplicate attributes, unsupported entities, resource exhaustion and malformed input must produce compiler errors, not browser-style repaired trees.
2. **No misleading HTML compatibility claim:** an angle-bracket grammar is not standard HTML semantics. Decide whether to be browser-parseable, strict XML-like, or a deliberately restricted HTML subset; record decision explicitly.
3. **One construct, one obvious meaning:** consistent evaluation order, integer widths, signedness, overflow policy, name resolution, encoding and error behavior.
4. **Good novice diagnostics:** filename + line/column + expected vs actual + actionable fix; no silent fallback to surprising behavior.
5. **Safe by default, unsafe explicit:** ordinary code cannot access arbitrary I/O ports, raw pointers or interrupt controls. Provide audited, typed APIs and require visible privilege boundaries for dangerous operations.
6. **Small native runtime:** no browser, Python, Node, JavaScript or garbage collector is needed **at kernel runtime** by default. Build-time Python/C toolchain is acceptable during prototyping and must be disclosed.
7. **Modules and reusable library:** avoid forcing long nested tags for everything. Favor readable APIs over merely reducing compiler implementation cost.
8. **Predictable compilation:** source order, typed AST, lowering, reproducible binary and target ABI; deterministic diagnostics on supported source.
9. **Portability is explicit:** first target x86-64 only. Endianness, alignment, MMIO, traps and ABI differ on future targets.
10. **Versioned language contract:** specify compatible syntax changes, breaking changes, fixture tests and migration examples rather than relying on HTML browser behavior.

## Comparative usability test (required before claiming Python-level ease)

Ask actual beginners to complete the same tasks with Python and the experimental dialect (without providing more help to one group). Tasks: print text; store/change a number; branch on an input; repeat a bounded operation; define/call a helper.

Measure:
- time to first correct result, number of errors and requested hints;
- clarity of error messages (beginner can point to exact fix);
- median lines/characters and **nested depth** for equivalent programs;
- whether unexpected unsafe behavior can be triggered without explicit permission.

Use matched environments and publish counts/methodology; avoid inventing percentages or superiority claims. **Until M2 exists, this benchmark is NOT RUN.**

## Open design decisions

- Standard-compatible HTML-like tags vs stricter dedicated grammar (browser parsing may silently normalize unexpected structures).
- Explicit integer types vs limited type inference; expression representation.
- C as an intermediate representation vs direct LLVM/native codegen.
- Ownership/borrow/checking/unsafe semantics and trusted runtime size.
- Whether to separate kernel-mode and userspace syntax/libraries or have one language with capability-restricted APIs.
- Debugger/source maps, module import paths and sandbox policy.

Track decisions in [DECISIONS.md](DECISIONS.md); evaluation gates in [ROADMAP.md](ROADMAP.md); source truth in [STATUS.md](STATUS.md).
