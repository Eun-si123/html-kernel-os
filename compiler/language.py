"""Strict, tiny HTML-shaped systems language front-end (M2 subset)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from html.parser import HTMLParser
import keyword
import re

UINT64_MAX = (1 << 64) - 1
UINT32_MAX = (1 << 32) - 1
INT_TYPES = {"u32", "u64"}
MAX_SOURCE_BYTES = 131072
MAX_NODES = 1024
MAX_OUTPUT_BYTES = 16384
MAX_RUNTIME_STEPS = 20000
MAX_LOOP_TIMES = 64
MAX_FUNCTIONS = 32
MAX_FUNCTION_ARGS = 4
MAX_FUNCTION_DEPTH = 8
NAME = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*\Z")
CHILDREN = {"kernel": {None}, "onboot": {"kernel"},
            "print": {"onboot", "if", "repeat", "else"},
            "let": {"onboot", "function", "if", "repeat", "else"},
            "set": {"onboot", "function", "if", "repeat", "else"},
            "if": {"onboot", "function", "if", "repeat", "else"},
            "repeat": {"onboot", "function", "if", "repeat", "else"},
            "halt": {"onboot"},
            "function": {"kernel"},
            "return": {"function", "if", "repeat", "else"},
            "else": {"if"}}
ALLOWED = {"kernel": {"arch"}, "onboot": set(), "print": {"value"},
           "let": {"name", "type", "value"}, "set": {"name", "value"},
           "if": {"test"}, "repeat": {"times"}, "halt": set(),
           "function": {"name", "params", "returns"}, "return": {"value"},
           "else": set()}
REQUIRED = {"let": {"name", "type", "value"}, "set": {"name", "value"},
            "if": {"test"}, "repeat": {"times"},
            "function": {"name", "params", "returns"}, "return": {"value"}}


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


@dataclass
class FunctionDef:
    name: str
    params: tuple[str, ...]
    return_node: Node
    source_node: Node
    body: list[Node]
    param_types: dict[str, str] = field(default_factory=dict)
    return_type: str = "u64"


@dataclass
class Program:
    statements: list[Node]
    functions: dict[str, FunctionDef]


class KernelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[Node] = []
        self.root_seen = False
        self.boot_seen = False
        self.halted = False
        self.program: list[Node] = []
        self.functions: list[Node] = []
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
        inside_function = any(item.tag == "function" for item in self.stack)
        if self.halted and any(item.tag == "onboot" for item in self.stack):
            fail(node, "no statements are allowed after <halt/>")
        if tag == "return" and not inside_function:
            fail(node, "<return> is only allowed inside a <function>")
        if tag == "let" and parent in {"if", "repeat", "else"} and not inside_function:
            fail(node, "block-scoped <let> is only supported inside functions")
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
        elif tag == "function":
            if validate_name(node) in INT_TYPES:
                fail(node, "u32 and u64 are reserved numeric conversion functions")
            if pairs["returns"] not in INT_TYPES:
                fail(node, 'only returns="u32" or returns="u64" is implemented')
        elif tag == "let":
            validate_name(node)
            if pairs["type"] not in INT_TYPES:
                fail(node, 'only type="u32" or type="u64" is implemented')
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
        if tag == "if":
            else_positions = [i for i, child in enumerate(node.children)
                              if child.tag == "else"]
            if len(else_positions) > 1:
                fail(node, "<if> may contain at most one <else>")
            if else_positions and else_positions[0] != len(node.children) - 1:
                fail(node, "<else> must be the final child of <if>")
        if tag == "onboot":
            self.program = node.children
        elif tag == "function":
            if not node.children or node.children[-1].tag != "return":
                fail(node, '<function> must end with a top-level <return value="..."/>')
            self.functions.append(node)
            if len(self.functions) > MAX_FUNCTIONS:
                fail(node, f"at most {MAX_FUNCTIONS} functions are supported")
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

    def finish(self) -> Program:
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
                elif node.tag in {"if", "repeat", "else"}:
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
        funcs: dict[str, FunctionDef] = {}
        for fn in self.functions:
            name = validate_name(fn)
            if name in funcs:
                fail(fn, f"function {name!r} already defined")
            raw = fn.attrs["params"].strip()
            parts = [] if not raw else [part.strip() for part in raw.split(",")]
            if len(parts) > MAX_FUNCTION_ARGS:
                fail(fn, f"function parameters exceed limit of {MAX_FUNCTION_ARGS}")
            params: list[str] = []
            types: dict[str, str] = {}
            for part in parts:
                bits = [bit.strip() for bit in part.split(":")]
                if len(bits) != 2 or bits[1] not in INT_TYPES or not NAME.fullmatch(bits[0]) or keyword.iskeyword(bits[0]):
                    fail(fn, f"bad typed parameter {part!r}; expected name:u32 or name:u64")
                if bits[0] in params:
                    fail(fn, f"duplicate parameter {bits[0]!r}")
                params.append(bits[0])
                types[bits[0]] = bits[1]
            # A top-level final return guarantees a value even when earlier
            # conditional branches or zero-iteration repeats do not execute.
            def check_return_order(nodes: list[Node]) -> None:
                # An <else> is a sibling marker within <if>, not a statement
                # executed after the then-branch. A branch ending in <return>
                # may legally have a following <else>.
                has_else = bool(nodes and nodes[-1].tag == "else")
                branch = nodes[:-1] if has_else else nodes
                for index, item in enumerate(branch):
                    if item.tag == "return" and index + 1 != len(branch):
                        fail(item, "statements after <return> are unreachable")
                    if item.tag in {"if", "repeat"}:
                        check_return_order(item.children)
                if has_else:
                    check_return_order(nodes[-1].children)
            check_return_order(fn.children)
            funcs[name] = FunctionDef(name, tuple(params), fn.children[-1], fn,
                                      fn.children, types, fn.attrs["returns"])
        return Program(self.program, funcs)


def parse(source: str) -> Program:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise CompileError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    parser = KernelParser()
    parser.source_lines = source.splitlines(keepends=True)
    parser.feed(source)
    parser.close()
    return parser.finish()


def expression(source: str, node: Node, variables: set[str] | dict[str, str],
               *, boolean: bool = False,
               functions: dict[str, FunctionDef] | None = None,
               calls: list[str] | None = None,
               variable_types: dict[str, str] | None = None,
               expected_type: str | None = None) -> str:
    """Emit C from typed expressions, rejecting implicit u32/u64 mixing.

    Literal-only expressions inherit an expected integer type, otherwise u64.
    u32(x) narrows modulo 2**32; u64(x) explicitly widens u32.
    Legacy u64 expressions preserve their original generated C spelling.
    """
    if not source or len(source.encode("utf-8")) > 256:
        fail(node, "expression must contain 1..256 UTF-8 bytes")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        fail(node, f"invalid expression {source!r}: {exc.msg}")
    if sum(1 for _ in ast.walk(tree)) > 64:
        fail(node, "expression too complex (over 64 AST nodes)")
    if expected_type is not None and expected_type not in INT_TYPES:
        fail(node, f"unsupported expression type {expected_type!r}")
    types = variable_types or {}
    funcs = functions or {}

    def numeric(a: str, b: str, *, operation: str) -> str:
        if a == "boolean" or b == "boolean":
            fail(node, f"{operation} operands must be u64 or u32")
        if a != "literal" and b != "literal" and a != b:
            fail(node, f"cannot mix {a} and {b} without explicit u32(...) or u64(...) conversion")
        return a if a != "literal" else b

    def kind(item: ast.AST) -> str:
        if isinstance(item, ast.Constant) and type(item.value) is int:
            if not 0 <= item.value <= UINT64_MAX:
                fail(node, "integer literal outside u64 range")
            return "literal"
        if isinstance(item, ast.Name):
            if item.id not in variables:
                fail(node, f"undefined variable {item.id!r}")
            return types.get(item.id, "u64")
        if isinstance(item, ast.Call):
            if not isinstance(item.func, ast.Name) or item.keywords:
                fail(node, "unsupported function call; expected a plain name and positional u64 arguments")
            name = item.func.id
            if name in INT_TYPES:
                if len(item.args) != 1:
                    fail(node, f"{name}(...) conversion expects exactly 1 argument")
                if kind(item.args[0]) == "boolean":
                    fail(node, f"{name}(...) conversion requires an integer")
                return name
            func = funcs.get(name)
            if func is None:
                fail(node, f"undefined function {name!r}")
            if len(item.args) != len(func.params):
                fail(node, f"function {name!r} expects {len(func.params)} arguments; got {len(item.args)}")
            for arg, param in zip(item.args, func.params):
                arg_type = kind(arg)
                param_type = func.param_types.get(param, "u64")
                if arg_type == "boolean":
                    fail(node, f"function arguments must be {param_type}")
                if arg_type not in ("literal", param_type):
                    fail(node, f"function {name!r} parameter {param!r} requires {param_type}; "
                         f"use explicit u32(...) or u64(...) conversion")
            return func.return_type
        if isinstance(item, ast.BinOp) and type(item.op) in (ast.Add, ast.Sub, ast.Mult):
            return numeric(kind(item.left), kind(item.right), operation="arithmetic")
        if isinstance(item, ast.Compare) and len(item.ops) == 1:
            left, right = kind(item.left), kind(item.comparators[0])
            numeric(left, right, operation="comparison")
            if type(item.ops[0]) not in (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE):
                fail(node, "comparison operator is not supported")
            return "boolean"
        if isinstance(item, ast.BoolOp) and type(item.op) in (ast.And, ast.Or):
            if any(kind(value) != "boolean" for value in item.values):
                fail(node, "boolean operators require comparisons")
            return "boolean"
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Not):
            if kind(item.operand) != "boolean":
                fail(node, "'not' requires a comparison")
            return "boolean"
        fail(node, f"unsupported expression syntax: {type(item).__name__}")

    root_kind = kind(tree.body)
    if boolean:
        if root_kind != "boolean":
            fail(node, f"expected boolean expression, got {'number' if root_kind != 'boolean' else root_kind}")
    elif root_kind == "boolean":
        fail(node, "expected number expression, got boolean")
    elif expected_type is not None and root_kind not in ("literal", expected_type):
        fail(node, f"expected {expected_type} expression but got {root_kind}; "
             f"use explicit {expected_type}(...) conversion")

    def emit(item: ast.AST, preferred: str | None = None) -> str:
        inferred = kind(item)
        if inferred not in ("literal", "boolean") and preferred not in (None, inferred):
            fail(node, f"expected {preferred} expression but got {inferred}; "
                 f"use explicit {preferred}(...) conversion")
        if isinstance(item, ast.Constant) and type(item.value) is int:
            resolved = preferred or "u64"
            if resolved == "u32":
                if item.value > UINT32_MAX:
                    fail(node, f"integer literal {item.value} outside u32 range; use u32(...) to truncate explicitly")
                return f"UINT32_C({item.value})"
            return f"UINT64_C({item.value})"
        if isinstance(item, ast.Name):
            return variables[item.id] if isinstance(variables, dict) else "htmlk_" + item.id
        if isinstance(item, ast.Call):
            name = item.func.id
            if name in INT_TYPES:
                # Conversion is explicit: narrowing is modulo 2**32.
                value = emit(item.args[0], None)
                return f"(({ 'uint32_t' if name == 'u32' else 'uint64_t' })({value}))"
            func = funcs[name]
            arguments = [emit(arg, func.param_types.get(param, "u64"))
                         for arg, param in zip(item.args, func.params)]
            if calls is not None:
                calls.append(name)
            return f"htmlk_fn_{name}(" + ", ".join(arguments) + ")"
        if isinstance(item, ast.BinOp):
            result_type = inferred if inferred != "literal" else (preferred or "u64")
            left = emit(item.left, result_type)
            right = emit(item.right, result_type)
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(item.op)]
            return f"(({ 'uint32_t' if result_type == 'u32' else 'uint64_t' })({left} {op} {right}))"
        if isinstance(item, ast.Compare):
            operand_type = numeric(kind(item.left), kind(item.comparators[0]),
                                   operation="comparison")
            operand_type = operand_type if operand_type != "literal" else "u64"
            left = emit(item.left, operand_type)
            right = emit(item.comparators[0], operand_type)
            ops = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<",
                   ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
            return f"({left} {ops[type(item.ops[0])]} {right})"
        if isinstance(item, ast.BoolOp):
            op = " && " if isinstance(item.op, ast.And) else " || "
            return "(" + op.join(emit(value) for value in item.values) + ")"
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Not):
            return f"(!{emit(item.operand)})"
        fail(node, f"unsupported expression syntax: {type(item).__name__}")

    return emit(tree.body, expected_type)
