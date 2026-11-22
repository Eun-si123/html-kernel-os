"""Strict, tiny HTML-shaped systems language front-end (M2 subset)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from html.parser import HTMLParser
import keyword
import re

UINT64_MAX = (1 << 64) - 1
MAX_SOURCE_BYTES = 131072
MAX_NODES = 1024
MAX_OUTPUT_BYTES = 16384
MAX_RUNTIME_STEPS = 20000
MAX_LOOP_TIMES = 64
NAME = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*\Z")
CHILDREN = {"kernel": {None}, "onboot": {"kernel"},
            "print": {"onboot", "if", "repeat"},
            "let": {"onboot"}, "set": {"onboot", "if", "repeat"},
            "if": {"onboot", "if", "repeat"},
            "repeat": {"onboot", "if", "repeat"},
            "halt": {"onboot"}}
ALLOWED = {"kernel": {"arch"}, "onboot": set(), "print": {"value"},
           "let": {"name", "type", "value"}, "set": {"name", "value"},
           "if": {"test"}, "repeat": {"times"}, "halt": set()}
REQUIRED = {"let": {"name", "type", "value"}, "set": {"name", "value"},
            "if": {"test"}, "repeat": {"times"}}


class CompileError(ValueError):
    """Invalid user source; includes a useful source position."""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    col: int
    children: list["Node"] = field(default_factory=list)
    text: list[str] = field(default_factory=list)


def fail(node: Node, message: str) -> None:
    raise CompileError(f"line {node.line}, column {node.col + 1}: {message}")


def validate_name(node: Node) -> str:
    name = node.attrs["name"]
    if not NAME.fullmatch(name) or keyword.iskeyword(name):
        fail(node, f"invalid variable name {name!r}; use ASCII letters, digits, underscore")
    return name


class KernelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[Node] = []
        self.root_seen = False
        self.boot_seen = False
        self.halted = False
        self.program: list[Node] = []
        self.nodes = 0
        self.saw_print = False
        self.source_lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, col = self.getpos()
        pairs = {k: v for k, v in attrs}
        node = Node(tag, pairs, line, col)
        parent = self.stack[-1].tag if self.stack else None
        if tag not in CHILDREN or parent not in CHILDREN[tag]:
            fail(node, f"<{tag}> is not allowed under <{parent}>")
        if self.halted:
            fail(node, "no statements are allowed after <halt/>")
        if len(pairs) != len(attrs):
            fail(node, f"duplicate attributes on <{tag}>")
        unknown = set(pairs) - ALLOWED[tag]
        missing = REQUIRED.get(tag, set()) - set(pairs)
        if unknown or missing or any(value is None for value in pairs.values()):
            fail(node, f"invalid attributes on <{tag}>; unknown={sorted(unknown)}, missing={sorted(missing)}")
        if tag == "kernel":
            if self.root_seen or pairs.get("arch", "x86_64") != "x86_64":
                fail(node, "only one <kernel arch=\"x86_64\"> is supported")
            self.root_seen = True
        elif tag == "onboot":
            if self.boot_seen:
                fail(node, "only one <onboot> is allowed")
            self.boot_seen = True
        elif tag == "let":
            validate_name(node)
            if pairs["type"] != "u64":
                fail(node, "only type=\"u64\" is implemented (unsigned 64-bit, wrapping arithmetic)")
        elif tag == "set":
            validate_name(node)
        elif tag == "repeat":
            count = pairs["times"]
            if not count.isascii() or not count.isdecimal() or len(count) > 3:
                fail(node, "repeat times must be a decimal integer between 0 and 64")
            if int(count) > MAX_LOOP_TIMES:
                fail(node, "repeat times must be between 0 and 64")
        self.nodes += 1
        if self.nodes > MAX_NODES or len(self.stack) >= 16:
            fail(node, "source contains too many nodes or deeply nested elements")
        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1].tag != tag:
            line, col = self.getpos()
            raise CompileError(f"line {line}, column {col + 1}: unexpected closing tag </{tag}>")
        node = self.stack.pop()
        if tag == "print":
            value = "".join(node.text)
            if "value" in node.attrs:
                if value:
                    fail(node, "<print value=\"...\"/> cannot contain text")
            elif not value or len(value.encode("utf-8")) > 4096:
                fail(node, "<print> must contain 1..4096 UTF-8 bytes")
            self.saw_print = True
        elif node.text:
            fail(node, f"text is only permitted inside <print>, not <{tag}>")
        if tag == "onboot":
            self.program = node.children
        elif tag == "halt":
            self.halted = True
        if self.stack:
            self.stack[-1].children.append(node)

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1].tag == "print":
            self.stack[-1].text.append(data)
        elif data.strip():
            line, col = self.getpos()
            raise CompileError(f"line {line}, column {col + 1}: text is only allowed inside <print>")

    def handle_comment(self, data: str) -> None:
        # HTMLParser calls handle_comment for malformed <!bogus> too.
        line, col = self.getpos()
        offset = sum(len(part) for part in self.source_lines[:line - 1]) + col
        tail = "".join(self.source_lines)[offset:]
        if not tail.startswith("<!--") or "-->" not in tail:
            raise CompileError("only complete <!-- ... --> comments are supported")
        if self.stack and self.stack[-1].tag == "print":
            fail(self.stack[-1], "comments within <print> are not supported")

    def handle_decl(self, decl: str) -> None:
        raise CompileError("declarations / DOCTYPE are not valid kernel source")

    def handle_pi(self, data: str) -> None:
        raise CompileError("processing instructions are not valid kernel source")

    def unknown_decl(self, data: str) -> None:
        raise CompileError("unknown declarations are not valid kernel source")

    def finish(self) -> list[Node]:
        if self.stack or not (self.root_seen and self.boot_seen):
            raise CompileError("expected closed <kernel><onboot>...</onboot></kernel>")
        if not self.saw_print:
            raise CompileError("at least one <print> is required")
        # Conservative bounds across nested repeats, including non-output work.
        def estimate(nodes: list[Node]) -> tuple[int, int]:
            output, steps = 0, 0
            for node in nodes:
                nout, nsteps = 0, 1
                if node.tag == "print":
                    nout = (21 if "value" in node.attrs
                            else len("".join(node.text).encode("utf-8")) + 1)
                elif node.tag in {"if", "repeat"}:
                    nested_out, nested_steps = estimate(node.children)
                    scale = int(node.attrs["times"]) if node.tag == "repeat" else 1
                    nout = scale * nested_out
                    nsteps += scale * nested_steps
                output += nout
                steps += nsteps
                if output > MAX_OUTPUT_BYTES:
                    fail(node, f"estimated output exceeds {MAX_OUTPUT_BYTES} bytes")
                if steps > MAX_RUNTIME_STEPS:
                    fail(node, f"estimated work exceeds {MAX_RUNTIME_STEPS} steps")
            return output, steps
        estimate(self.program)
        return self.program


def parse(source: str) -> list[Node]:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise CompileError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    parser = KernelParser()
    parser.source_lines = source.splitlines(keepends=True)
    parser.feed(source)
    parser.close()
    return parser.finish()


def expression(source: str, node: Node, variables: set[str], *, boolean: bool = False) -> str:
    if not source or len(source.encode("utf-8")) > 256:
        fail(node, "expression must contain 1..256 UTF-8 bytes")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        fail(node, f"invalid expression {source!r}: {exc.msg}")
    if sum(1 for _ in ast.walk(tree)) > 64:
        fail(node, "expression too complex (over 64 AST nodes)")

    def emit(item: ast.AST) -> tuple[str, str]:
        if isinstance(item, ast.Constant) and type(item.value) is int:
            if not 0 <= item.value <= UINT64_MAX:
                fail(node, "integer literal outside u64 range")
            return f"UINT64_C({item.value})", "number"
        if isinstance(item, ast.Name):
            if item.id not in variables:
                fail(node, f"undefined variable {item.id!r}")
            return "htmlk_" + item.id, "number"
        if isinstance(item, ast.BinOp) and type(item.op) in (ast.Add, ast.Sub, ast.Mult):
            left, lt = emit(item.left)
            right, rt = emit(item.right)
            if (lt, rt) != ("number", "number"):
                fail(node, "arithmetic operands must be u64")
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(item.op)]
            return f"((uint64_t)({left} {op} {right}))", "number"
        if isinstance(item, ast.Compare) and len(item.ops) == 1:
            left, lt = emit(item.left)
            right, rt = emit(item.comparators[0])
            if (lt, rt) != ("number", "number"):
                fail(node, "comparison operands must be u64")
            ops = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<",
                   ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
            op = ops.get(type(item.ops[0]))
            if op is None:
                fail(node, "comparison operator is not supported")
            return f"({left} {op} {right})", "boolean"
        if isinstance(item, ast.BoolOp) and type(item.op) in (ast.And, ast.Or):
            values = [emit(value) for value in item.values]
            if any(kind != "boolean" for _, kind in values):
                fail(node, "boolean operators require comparisons")
            op = " && " if isinstance(item.op, ast.And) else " || "
            return "(" + op.join(expr for expr, _ in values) + ")", "boolean"
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Not):
            value, kind = emit(item.operand)
            if kind != "boolean":
                fail(node, "'not' requires a comparison")
            return f"(!{value})", "boolean"
        fail(node, f"unsupported expression syntax: {type(item).__name__}")

    result, kind = emit(tree.body)
    expected = "boolean" if boolean else "number"
    if kind != expected:
        fail(node, f"expected {expected} expression, got {kind}")
    return result
