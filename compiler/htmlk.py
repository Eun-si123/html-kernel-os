#!/usr/bin/env python3
"""Compile an HTML-shaped systems language to x86-64 kernel or Linux C."""
from __future__ import annotations

import argparse
from pathlib import Path

if __package__:
    from .language import CompileError, MAX_RUNTIME_STEPS, Node, expression, fail, parse, validate_name, array_code, array_details
    from .function_codegen import compile_functions
    from .numeric_types import c_type, c_helpers
else:
    from language import CompileError, MAX_RUNTIME_STEPS, Node, expression, fail, parse, validate_name, array_code, array_details
    from function_codegen import compile_functions
    from numeric_types import c_type, c_helpers


def compile_html(source: str, *, target: str = "kernel") -> str:
    if target not in ("kernel", "linux"):
        raise CompileError(f"unknown compiler target {target!r}")
    parsed = parse(source)
    program = parsed.statements
    functions = parsed.functions
    contains_numeric_print = False
    contains_arrays = False

    def scan(nodes: list[Node]) -> None:
        nonlocal contains_numeric_print, contains_arrays
        for node in nodes:
            contains_numeric_print |= node.tag == "print" and "value" in node.attrs
            contains_arrays |= node.tag == "array"
            scan(node.children)
    scan(program)
    for fn in functions.values():
        scan(fn.body)

    lines = [
        "/* Generated from HTML Kernel language. x86-64 native C. */",
        "#include <stdint.h>",
        "#if !defined(__x86_64__)",
        '#error "x86_64 only"',
        "#endif",
    ]
    if target == "kernel":
        lines += [
        "static inline void io_outb(unsigned short port, unsigned char v) {",
        '  __asm__ volatile ("outb %0, %1" : : "a"(v), "Nd"(port));',
        "}",
        "static inline void serial_init(void) {",
        "  io_outb(0x3f9, 0x00); io_outb(0x3fb, 0x80);",
        "  io_outb(0x3f8, 0x03); io_outb(0x3f9, 0x00);",
        "  io_outb(0x3fb, 0x03); io_outb(0x3fa, 0xc7); io_outb(0x3fc, 0x0b);",
        "}",
        "#ifdef HTMLK_FB_CONSOLE",
        "extern void htmlk_fb_putchar(uint8_t v);",
        "#endif",
        "static inline void outb(unsigned char v) {",
        "  io_outb(0xe9, v); /* QEMU debugcon */",
        "  io_outb(0x3f8, v); /* COM1 */",
        "#ifdef HTMLK_FB_CONSOLE",
        "  htmlk_fb_putchar(v); /* real mapped Limine RGB framebuffer */",
        "#endif",
        "}",
        ]
    else:
        lines += [
            "#include <stdio.h>",
            "static inline void outb(unsigned char v) {",
            "  (void)putchar((int)v); /* Linux userspace stdout, NOT port I/O */",
            "}",
        ]
    # Division and remainder must never invoke C undefined behavior. The
    # fault path is target-specific and deliberately does not silently return.
    if target == "kernel":
        lines += [
            "static inline __attribute__((noreturn)) void htmlk_divide_by_zero(void) {",
            "  const unsigned char msg[] = \"HTMLK_DIVIDE_BY_ZERO\\n\";",
            "  for (uint64_t i = 0; i < sizeof(msg) - 1; ++i) outb(msg[i]);",
            "#ifdef HTMLK_QEMU_TEST_EXIT",
            "  io_outb(0xf4, 0x11); /* QEMU failure exit, never success */",
            "#endif",
            '  __asm__ volatile ("cli");',
            '  for (;;) __asm__ volatile ("hlt");',
            "}",
        ]
    else:
        lines += [
            "#include <stdlib.h>",
            "static inline __attribute__((noreturn)) void htmlk_divide_by_zero(void) {",
            '  (void)fputs("HTMLK_DIVIDE_BY_ZERO\\n", stderr);',
            "  exit(65);",
            "}",
        ]
    if contains_arrays:
        if target == "kernel":
            lines += [
                "static inline __attribute__((noreturn)) void htmlk_array_bounds_fault(void) {",
                '  const unsigned char msg[] = "HTMLK_ARRAY_BOUNDS\\n";',
                "  for (uint64_t i = 0; i < sizeof(msg) - 1; ++i) outb(msg[i]);",
                "#ifdef HTMLK_QEMU_TEST_EXIT",
                "  io_outb(0xf4, 0x12); /* non-success QEMU exit 37 */",
                "#endif",
                '  __asm__ volatile ("cli");',
                '  for (;;) __asm__ volatile ("hlt");',
                "}",
            ]
        else:
            lines += [
                "static inline __attribute__((noreturn)) void htmlk_array_bounds_fault(void) {",
                '  (void)fputs("HTMLK_ARRAY_BOUNDS\\n", stderr);',
                "  exit(66);",
                "}",
            ]
        lines += [
            "static inline uint64_t htmlk_checked_index(uint64_t index, uint64_t length) {",
            "  if (index >= length) htmlk_array_bounds_fault();",
            "  return index;",
            "}",
        ]
    lines.extend(c_helpers())
    if contains_numeric_print:
        lines += [
            "static void htmlk_print_u64(uint64_t value) {",
            "  unsigned char buffer[20];",
            "  unsigned count = 0;",
            "  do {",
            "    buffer[count++] = (unsigned char)('0' + (value % UINT64_C(10)));",
            "    value /= UINT64_C(10);",
            "  } while (value != 0);",
            "  while (count) outb(buffer[--count]);",
            "  outb(10);",
            "}",
            "static inline void htmlk_print_i64(int64_t value) {",
            "  if (value < 0) {",
            "    outb('-');",
            "    htmlk_print_u64(UINT64_C(0) - (uint64_t)value);",
            "  } else {",
            "    htmlk_print_u64((uint64_t)value);",
            "  }",
            "}",
        ]
    definitions, costs = compile_functions(functions)
    lines.extend(definitions)
    lines.append("void kernel_main(void) {" if target == "kernel"
                 else "int main(void) {")
    if target == "kernel":
        lines.append("  serial_init();")
    variables: set[str] = set()
    variable_types: dict[str, str] = {}
    loop_id = 0
    work_done = 0

    def statements(nodes: list[Node], indent: int = 1, multiplier: int = 1) -> None:
        nonlocal loop_id, work_done
        pad = "  " * indent
        for node in nodes:
            tag = node.tag
            work_done += multiplier
            if work_done > MAX_RUNTIME_STEPS:
                fail(node, "runtime statement budget exceeded")
            def checked(source: str, *, boolean: bool = False,
                        expected_type: str | None = None,
                        type_out: list[str] | None = None,
                        evaluations: int = 1) -> str:
                nonlocal work_done
                called: list[str] = []
                result = expression(source, node, variables,
                                    boolean=boolean, functions=functions, calls=called,
                                    variable_types=variable_types, expected_type=expected_type,
                                    type_out=type_out)
                work_done += multiplier * evaluations * sum(costs[name] for name in called)
                if work_done > MAX_RUNTIME_STEPS:
                    fail(node, "expanded function work budget exceeded")
                return result
            if tag == "print":
                if "value" in node.attrs:
                    detected: list[str] = []
                    value = checked(node.attrs["value"], type_out=detected)
                    if detected[0] in {"i32", "i64"}:
                        lines.append(f"{pad}htmlk_print_i64((int64_t)({value}));")
                    else:
                        lines.append(f"{pad}htmlk_print_u64({value});")
                else:
                    data = ", ".join(f"0x{b:02x}" for b in
                                     ("".join(node.text) + "\n").encode("utf-8"))
                    lines.extend([
                        f"{pad}{{",
                        f"{pad}  const unsigned char message[] = {{{data}}};",
                        f"{pad}  for (uint64_t i = 0; i < sizeof(message); ++i) outb(message[i]);",
                        f"{pad}}}",
                    ])
            elif tag == "let":
                name = validate_name(node)
                if name in variables:
                    fail(node, f"variable {name!r} is already declared")
                typ = node.attrs["type"]
                value = checked(node.attrs["value"], expected_type=typ)
                variables.add(name)
                variable_types[name] = typ
                ctype = c_type(typ)
                lines.append(f"{pad}{ctype} htmlk_{name} = {value};")
                # An unused declaration is legal source, not a C -Werror failure.
                lines.append(f"{pad}(void)htmlk_{name};")
            elif tag == "array":
                name = validate_name(node)
                if name in variables:
                    fail(node, f"variable {name!r} is already declared")
                typ = node.attrs["type"]
                size = int(node.attrs["length"])
                variables.add(name)
                variable_types[name] = array_code(typ, size)
                lines.extend([
                    f"{pad}{c_type(typ)} htmlk_{name}[{size}] = {{0}};",
                    f"{pad}(void)htmlk_{name};",
                ])
            elif tag == "store":
                name = validate_name(node)
                detail = array_details(variable_types.get(name, ""))
                if detail is None:
                    fail(node, f"undefined array {name!r}; declare <array> first")
                element, _ = detail
                location = checked(f"{name}[{node.attrs['index']}]", expected_type=element)
                value = checked(node.attrs["value"], expected_type=element)
                lines.append(f"{pad}{location} = {value};")
            elif tag == "set":
                name = validate_name(node)
                if name not in variables:
                    fail(node, f"undefined variable {name!r}")
                if array_details(variable_types[name]) is not None:
                    fail(node, f"array {name!r} requires an indexed element; use <store>")
                value = checked(node.attrs["value"], expected_type=variable_types[name])
                lines.append(f"{pad}htmlk_{name} = {value};")
            elif tag == "if":
                test = checked(node.attrs["test"], boolean=True)
                alternate = (node.children[-1] if node.children and
                             node.children[-1].tag == "else" else None)
                true_body = node.children[:-1] if alternate else node.children
                lines.append(f"{pad}if ({test}) {{")
                statements(true_body, indent + 1, multiplier)
                if alternate is not None:
                    lines.append(f"{pad}}} else {{")
                    statements(alternate.children, indent + 1, multiplier)
                lines.append(f"{pad}}}")
            elif tag == "repeat":
                count = int(node.attrs["times"])
                temp = f"htmlk_loop_{loop_id}"
                loop_id += 1
                lines.append(f"{pad}for (uint64_t {temp} = 0;"
                             f" {temp} < UINT64_C({count}); ++{temp}) {{")
                statements(node.children, indent + 1, multiplier * count)
                lines.append(f"{pad}}}")
            elif tag == "while":
                count = int(node.attrs["max"])
                test = checked(node.attrs["test"], boolean=True, evaluations=count)
                # Bound guard checks as well as statements, including early exit.
                work_done += multiplier * count
                if work_done > MAX_RUNTIME_STEPS:
                    fail(node, "runtime statement budget exceeded")
                temp = f"htmlk_loop_{loop_id}"
                loop_id += 1
                lines.append(f"{pad}for (uint64_t {temp} = 0;"
                             f" {temp} < UINT64_C({count}) && ({test}); ++{temp}) {{")
                statements(node.children, indent + 1, multiplier * count)
                lines.append(f"{pad}}}")
            elif tag == "break":
                lines.append(f"{pad}break;")
            elif tag == "continue":
                lines.append(f"{pad}continue;")
            elif tag == "halt":
                # The parser enforces that halt is the final top-level statement.
                break
            else:
                fail(node, f"compiler does not implement <{tag}>")
    statements(program)
    if target == "kernel":
        lines += [
        "#ifdef HTMLK_FB_TEST",
        "  extern void htmlk_fb_verify_probe(void);",
        "  htmlk_fb_verify_probe();",
        "#endif",
        "#ifdef HTMLK_QEMU_TEST_EXIT",
        "  /* Only test kernels write deterministic QEMU success port. */",
        '  __asm__ volatile ("outb %0, %1" : : "a"((unsigned char)0x10),',
        '                    "Nd"((unsigned short)0xf4));',
        "#endif",
        '  __asm__ volatile ("cli");',
        '  for (;;) __asm__ volatile ("hlt");',
        ]
    else:
        lines += ["  return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;"]
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile HTML Kernel source to native kernel or Linux C")
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target", choices=("kernel", "linux"), default="kernel",
                    help="Kernel: privileged I/O and halt; Linux: stdout and normal exit")
    args = ap.parse_args()
    try:
        generated = compile_html(args.input.read_text(encoding="utf-8"),
                                 target=args.target)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(generated, encoding="utf-8")
    except (CompileError, OSError, UnicodeError) as exc:
        ap.error(f"{args.input}: {exc}")
    print(f"Generated {args.out} ({args.target} x86-64 C source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
