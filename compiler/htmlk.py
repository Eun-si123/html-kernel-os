#!/usr/bin/env python3
"""Compile an HTML-shaped systems language to freestanding x86-64 C."""
from __future__ import annotations

import argparse
from pathlib import Path

if __package__:
    from .language import CompileError, Node, expression, fail, parse, validate_name
else:
    from language import CompileError, Node, expression, fail, parse, validate_name


def compile_html(source: str) -> str:
    program = parse(source)
    contains_numeric_print = False

    def scan(nodes: list[Node]) -> None:
        nonlocal contains_numeric_print
        for node in nodes:
            contains_numeric_print |= node.tag == "print" and "value" in node.attrs
            scan(node.children)
    scan(program)

    lines = [
        "/* Generated from HTML Kernel language. Freestanding x86-64 C. */",
        "#include <stdint.h>",
        "#if !defined(__x86_64__)",
        '#error "x86_64 only"',
        "#endif",
        "static inline void io_outb(unsigned short port, unsigned char v) {",
        '  __asm__ volatile ("outb %0, %1" : : "a"(v), "Nd"(port));',
        "}",
        "static inline void serial_init(void) {",
        "  io_outb(0x3f9, 0x00); io_outb(0x3fb, 0x80);",
        "  io_outb(0x3f8, 0x03); io_outb(0x3f9, 0x00);",
        "  io_outb(0x3fb, 0x03); io_outb(0x3fa, 0xc7); io_outb(0x3fc, 0x0b);",
        "}",
        "static inline void outb(unsigned char v) {",
        "  io_outb(0xe9, v); /* QEMU debugcon */",
        "  io_outb(0x3f8, v); /* COM1 */",
        "}",
    ]
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
        ]
    lines += ["void kernel_main(void) {", "  serial_init();"]
    variables: set[str] = set()
    loop_id = 0

    def statements(nodes: list[Node], indent: int = 1) -> None:
        nonlocal loop_id
        pad = "  " * indent
        for node in nodes:
            tag = node.tag
            if tag == "print":
                if "value" in node.attrs:
                    value = expression(node.attrs["value"], node, variables)
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
                value = expression(node.attrs["value"], node, variables)
                variables.add(name)
                lines.append(f"{pad}uint64_t htmlk_{name} = {value};")
                # An unused declaration is legal source, not a C -Werror failure.
                lines.append(f"{pad}(void)htmlk_{name};")
            elif tag == "set":
                name = validate_name(node)
                if name not in variables:
                    fail(node, f"undefined variable {name!r}")
                value = expression(node.attrs["value"], node, variables)
                lines.append(f"{pad}htmlk_{name} = {value};")
            elif tag == "if":
                test = expression(node.attrs["test"], node, variables, boolean=True)
                lines.append(f"{pad}if ({test}) {{")
                statements(node.children, indent + 1)
                lines.append(f"{pad}}}")
            elif tag == "repeat":
                count = int(node.attrs["times"])
                temp = f"htmlk_loop_{loop_id}"
                loop_id += 1
                lines.append(f"{pad}for (uint64_t {temp} = 0;"
                             f" {temp} < UINT64_C({count}); ++{temp}) {{")
                statements(node.children, indent + 1)
                lines.append(f"{pad}}}")
            elif tag == "halt":
                # The parser enforces that halt is the final top-level statement.
                break
            else:
                fail(node, f"compiler does not implement <{tag}>")
    statements(program)
    lines += [
        "#ifdef HTMLK_QEMU_TEST_EXIT",
        "  /* Only test kernels write deterministic QEMU success port. */",
        '  __asm__ volatile ("outb %0, %1" : : "a"((unsigned char)0x10),',
        '                    "Nd"((unsigned short)0xf4));',
        "#endif",
        '  __asm__ volatile ("cli");',
        '  for (;;) __asm__ volatile ("hlt");',
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile HTML Kernel source to native freestanding C")
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        generated = compile_html(args.input.read_text(encoding="utf-8"))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(generated, encoding="utf-8")
    except (CompileError, OSError, UnicodeError) as exc:
        ap.error(str(exc))
    print(f"Generated {args.out} (freestanding C; use scripts/build_boot.py for boot ISO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
