"""Strict, tiny HTML-shaped systems language front-end (M2 subset)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from html.parser import HTMLParser
import keyword
import re

if __package__:
    from .numeric_types import (
        INTEGER_TYPE_SET, SIGNED_TYPES, UNSIGNED_TYPES,
        width, c_type, literal_macro,
    )
else:
    from numeric_types import (
        INTEGER_TYPE_SET, SIGNED_TYPES, UNSIGNED_TYPES,
        width, c_type, literal_macro,
    )

UINT64_MAX = (1 << 64) - 1
UINT32_MAX = (1 << 32) - 1
INT_TYPES = INTEGER_TYPE_SET
MAX_SOURCE_BYTES = 131072
MAX_NODES = 1024
MAX_OUTPUT_BYTES = 16384
MAX_RUNTIME_STEPS = 20000
MAX_LOOP_TIMES = 64
MAX_ARRAY_LENGTH = 64
MAX_ARRAY_DECLS = 16
MAX_FUNCTIONS = 32
MAX_FUNCTION_ARGS = 4
MAX_FUNCTION_DEPTH = 8
NAME = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*\Z")
CHILDREN = {"kernel": {None}, "onboot": {"kernel"},
            "print": {"onboot", "if", "repeat", "while", "else"},
            "let": {"onboot", "function", "if", "repeat", "while", "else"},
            "array": {"onboot", "function", "if", "repeat", "while", "else"},
            "store": {"onboot", "function", "if", "repeat", "while", "else"},
            "set": {"onboot", "function", "if", "repeat", "while", "else"},
            "if": {"onboot", "function", "if", "repeat", "while", "else"},
            "repeat": {"onboot", "function", "if", "repeat", "while", "else"},
            "while": {"onboot", "function", "if", "repeat", "while", "else"},
            "halt": {"onboot"},
            "function": {"kernel"},
            "return": {"function", "if", "repeat", "while", "else"},
            "else": {"if"},
            "break": {"repeat", "while", "if", "else"},
            "continue": {"repeat", "while", "if", "else"}}
ALLOWED = {"kernel": {"arch"}, "onboot": set(), "print": {"value"},
           "let": {"name", "type", "value"}, "set": {"name", "value"},
           "array": {"name", "type", "length"}, "store": {"name", "index", "value"},
           "if": {"test"}, "repeat": {"times"}, "while": {"test", "max"}, "halt": {"code"},
           "function": {"name", "params", "returns"}, "return": {"value"},
           "else": set(), "break": set(), "continue": set()}
REQUIRED = {"let": {"name", "type", "value"}, "set": {"name", "value"},
            "array": {"name", "type", "length"}, "store": {"name", "index", "value"},
            "if": {"test"}, "repeat": {"times"}, "while": {"test", "max"},
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


def array_code(kind: str, length: int) -> str:
    """Internal-only symbolic type, never accepted as a user scalar type."""
    return f"array:{kind}:{length}"


def array_details(kind: str) -> tuple[str, int] | None:
    if not kind.startswith("array:"):
        return None
    _, element, length = kind.split(":")
    return element, int(length)


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
        self.array_declarations = 0
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
        if tag in {"break", "continue"} and not any(item.tag in {"repeat", "while"} for item in self.stack):
            fail(node, f"<{tag}> requires an enclosing <repeat> or <while>")
        if tag in {"let", "array"} and parent in {"if", "repeat", "while", "else"} and not inside_function:
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
                fail(node, "integer type names are reserved numeric conversion functions")
            if pairs["returns"] not in INT_TYPES:
                fail(node, "only returns=u32/u64/i32/i64 is implemented")
        elif tag == "let":
            validate_name(node)
            if pairs["type"] not in INT_TYPES:
                fail(node, "only type=u32/u64/i32/i64 is implemented")
        elif tag == "array":
            validate_name(node)
            if pairs["type"] not in INT_TYPES:
                fail(node, "array type must be u32/u64/i32/i64")
            size = pairs["length"]
            if not size.isascii() or not size.isdecimal() or len(size) > 3 or not 1 <= int(size) <= MAX_ARRAY_LENGTH:
                fail(node, f"array length must be a decimal integer between 1 and {MAX_ARRAY_LENGTH}")
            self.array_declarations += 1
            if self.array_declarations > MAX_ARRAY_DECLS:
                fail(node, f"at most {MAX_ARRAY_DECLS} bounded arrays are supported")
        elif tag in {"set", "store"}:
            validate_name(node)
        elif tag == "halt" and "code" in pairs:
            # M5-F4: bounded numeric user exit status. The backend rejects
            # the attribute on kernel/Linux targets, never silently ignores.
            value = pairs["code"]
            if not (value.isascii() and value.isdecimal() and
                    len(value) <= 3 and 0 <= int(value) <= 255):
                fail(node, "halt code must be a decimal integer between 0 and 255")
        elif tag in {"repeat", "while"}:
            limit_attr = "times" if tag == "repeat" else "max"
            count = pairs[limit_attr]
            if not count.isascii() or not count.isdecimal() or len(count) > 3:
                fail(node, f"{tag} {limit_attr} must be a decimal integer between 0 and 64")
            if int(count) > MAX_LOOP_TIMES:
                fail(node, f"{tag} {limit_attr} must be between 0 and 64")
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
                elif node.tag in {"if", "repeat", "while", "else"}:
                    nested_out, nested_steps = estimate(node.children)
                    scale = (int(node.attrs["times"]) if node.tag == "repeat" else
                             int(node.attrs["max"]) if node.tag == "while" else 1)
                    nout = scale * nested_out
                    nsteps += scale * nested_steps
                    if node.tag == "while":
                        # At most max condition evaluations, including early exits.
                        nsteps += scale
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
                    fail(fn, f"bad typed parameter {part!r}; expected name:u32/u64/i32/i64")
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
                    if item.tag in {"return", "break", "continue"} and index + 1 != len(branch):
                        fail(item, f"statements after <{item.tag}> are unreachable")
                    if item.tag in {"if", "repeat", "while"}:
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
               expected_type: str | None = None,
               type_out: list[str] | None = None) -> str:
    """Typecheck/emit arithmetic as C11 without overflowing signed C integers.

    Unsigned values use modulo-2**width; signed i32/i64 arithmetic uses the
    same bit-pattern wrap with explicit signed interpretation. Conversions
    between all four widths require i32(...), i64(...), u32(...) or u64(...).
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
    literals = {"literal", "negative_literal"}
    signed = {"i32", "i64"}
    unsigned = {"u32", "u64"}

    def require_pair(a: str, b: str, operation: str) -> str:
        if a == "boolean" or b == "boolean":
            fail(node, f"{operation} operands must be integers, not boolean")
        if a not in literals and b not in literals and a != b:
            fail(node, f"cannot mix {a} and {b} without an explicit conversion")
        if a in literals and b in literals:
            return "negative_literal" if "negative_literal" in (a, b) else "literal"
        return a if a not in literals else b

    def explicit_zero(item: ast.AST) -> bool:
        """Recognize literal zero, parentheses, signs and explicit width casts."""
        if isinstance(item, ast.Constant) and type(item.value) is int:
            return item.value == 0
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, (ast.UAdd, ast.USub)):
            return explicit_zero(item.operand)
        if (isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                and item.func.id in INT_TYPES and len(item.args) == 1
                and not item.keywords):
            return explicit_zero(item.args[0])
        return False

    def kind(item: ast.AST) -> str:
        if isinstance(item, ast.Subscript):
            if not isinstance(item.value, ast.Name):
                fail(node, "only a declared array can be indexed")
            name = item.value.id
            detail = array_details(types.get(name, ""))
            if name not in variables or detail is None:
                fail(node, f"undefined array {name!r}; declare <array> first")
            element, length = detail
            index_type = kind(item.slice)
            if index_type not in unsigned | {"literal"}:
                fail(node, "array index must be u32/u64 or a non-negative integer literal")
            # Reject immediate out-of-range indices during compilation, including
            # explicit width conversions and a redundant unary plus.
            def static_index(expr: ast.AST) -> int | None:
                if isinstance(expr, ast.Constant) and type(expr.value) is int:
                    return expr.value
                if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.UAdd):
                    return static_index(expr.operand)
                if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name)
                        and expr.func.id in unsigned and len(expr.args) == 1
                        and not expr.keywords):
                    return static_index(expr.args[0])
                return None
            constant = static_index(item.slice)
            if constant is not None and constant >= length:
                fail(node, f"array index {constant} out of bounds for length {length}")
            return element
        if isinstance(item, ast.Constant) and type(item.value) is int:
            if not 0 <= item.value <= UINT64_MAX:
                fail(node, "integer literal outside u64 range")
            return "literal"
        if isinstance(item, ast.Name):
            if item.id not in variables:
                fail(node, f"undefined variable {item.id!r}")
            item_type = types.get(item.id, "u64")
            if array_details(item_type) is not None:
                fail(node, f"array {item.id!r} requires an indexed element; use {item.id}[index]")
            return item_type
        if isinstance(item, ast.Call):
            if not isinstance(item.func, ast.Name) or item.keywords:
                fail(node, "unsupported function call; expected a plain name and positional integer arguments")
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
                actual = kind(arg)
                required = func.param_types.get(param, "u64")
                if actual == "boolean":
                    fail(node, f"function arguments must be {required}")
                if actual not in literals and actual != required:
                    fail(node, f"function {name!r} parameter {param!r} requires {required}; use explicit {required}(...) conversion")
            return func.return_type
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.USub):
            inner = kind(item.operand)
            if inner == "literal":
                return "negative_literal"
            if inner in signed:
                return inner
            fail(node, "unary minus requires a signed i32/i64 value or literal")
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.UAdd):
            inner = kind(item.operand)
            if inner == "boolean":
                fail(node, "unary plus requires an integer")
            return inner
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Invert):
            inner = kind(item.operand)
            if inner not in unsigned and inner != "literal":
                fail(node, "bitwise NOT requires an unsigned integer; cast using u32(...) or u64(...)")
            return inner
        if isinstance(item, ast.BinOp):
            op = type(item.op)
            if op not in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.BitAnd,
                          ast.BitOr, ast.BitXor, ast.LShift, ast.RShift):
                fail(node, "unsupported binary operator")
            result = require_pair(kind(item.left), kind(item.right), "arithmetic")
            if op in (ast.Div, ast.Mod) and explicit_zero(item.right):
                fail(node, "division or remainder by zero literal")
            if op in (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift):
                if result in signed or result == "negative_literal":
                    fail(node, "bitwise operations require unsigned integers; cast using u32(...) or u64(...)")
            return result
        if isinstance(item, ast.Compare) and len(item.ops) == 1:
            require_pair(kind(item.left), kind(item.comparators[0]), "comparison")
            if type(item.ops[0]) not in (ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
                                         ast.Gt, ast.GtE):
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
    actual_type = (root_kind if root_kind not in literals
                   else expected_type or ("i64" if root_kind == "negative_literal" else "u64"))
    if boolean:
        if root_kind != "boolean":
            fail(node, "expected boolean expression, got number")
    elif root_kind == "boolean":
        fail(node, "expected number expression, got boolean")
    elif expected_type is not None and root_kind not in literals and root_kind != expected_type:
        fail(node, f"expected {expected_type} expression but got {root_kind}; use explicit {expected_type}(...) conversion")

    def emit(item: ast.AST, preferred: str | None = None) -> str:
        inferred = kind(item)
        if inferred not in literals | {"boolean"} and preferred not in (None, inferred):
            fail(node, f"expected {preferred} expression but got {inferred}; use explicit {preferred}(...) conversion")
        if isinstance(item, ast.Constant) and type(item.value) is int:
            resolved = preferred or "u64"
            limit = (1 << (width(resolved) - (1 if resolved in signed else 0))) - 1
            if item.value > limit:
                fail(node, f"integer literal {item.value} outside {resolved} range; use an explicit numeric conversion")
            return f"{literal_macro(resolved)}({item.value})"
        if isinstance(item, ast.Subscript):
            name = item.value.id  # kind() already restricted this to a declared array.
            _, length = array_details(types[name])
            symbol = variables[name] if isinstance(variables, dict) else "htmlk_" + name
            index_type = kind(item.slice)
            index = emit(item.slice, "u64" if index_type == "literal" else None)
            return f"{symbol}[htmlk_checked_index((uint64_t)({index}), UINT64_C({length}))]"
        if isinstance(item, ast.Name):
            return variables[item.id] if isinstance(variables, dict) else "htmlk_" + item.id
        if isinstance(item, ast.UnaryOp):
            if isinstance(item.op, ast.USub):
                resolved = inferred if inferred not in literals else (preferred or "i64")
                if resolved not in signed:
                    fail(node, "negative literal requires signed i32/i64 type or an explicit conversion")
                if isinstance(item.operand, ast.Constant) and type(item.operand.value) is int:
                    value = item.operand.value
                    limit = 1 << (width(resolved) - 1)
                    if value > limit:
                        fail(node, f"negative integer literal -{value} outside {resolved} range")
                    # -INT{width}_MIN cannot be represented as a positive C literal.
                    if value == limit:
                        largest = limit - 1
                        macro = literal_macro(resolved)
                        return f"(-{macro}({largest}) - {macro}(1))"
                    return f"(-{literal_macro(resolved)}({value}))"
                if inferred not in signed:
                    fail(node, "unary minus requires signed type")
                return f"htmlk_neg_{resolved}({emit(item.operand, resolved)})"
            if isinstance(item.op, ast.UAdd):
                return emit(item.operand, preferred)
            if isinstance(item.op, ast.Invert):
                resolved = inferred if inferred not in literals else (preferred or "u64")
                if resolved not in unsigned:
                    fail(node, "bitwise NOT requires unsigned u32/u64")
                return f"(({c_type(resolved)})(~{emit(item.operand, resolved)}))"
        if isinstance(item, ast.Call):
            name = item.func.id
            if name in INT_TYPES:
                argument = emit(item.args[0], None)
                if name in signed:
                    return f"htmlk_from_bits_{name}((uint{width(name)}_t)({argument}))"
                # Keep legacy u32/u64 codegen shape stable.
                return f"(({c_type(name)})({argument}))"
            func = funcs[name]
            args = [emit(arg, func.param_types.get(param, "u64"))
                    for arg, param in zip(item.args, func.params)]
            if calls is not None:
                calls.append(name)
            return f"htmlk_fn_{name}(" + ", ".join(args) + ")"
        if isinstance(item, ast.BinOp):
            resolved = inferred if inferred not in literals else (
                preferred or ("i64" if inferred == "negative_literal" else "u64")
            )
            left = emit(item.left, resolved)
            right = emit(item.right, resolved)
            operator = type(item.op)
            if operator in (ast.Add, ast.Sub, ast.Mult):
                op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[operator]
                if resolved in signed:
                    helper = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul"}[operator]
                    return f"htmlk_{helper}_{resolved}({left}, {right})"
                return f"(({c_type(resolved)})({left} {op} {right}))"
            if operator in (ast.Div, ast.Mod):
                helper = "div" if operator == ast.Div else "mod"
                return f"htmlk_{helper}_{resolved}({left}, {right})"
            if resolved not in unsigned:
                fail(node, "bitwise operations require u32/u64; use an explicit conversion")
            op = {ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^"}.get(operator)
            if op is not None:
                return f"(({c_type(resolved)})({left} {op} {right}))"
            helper = "shl" if operator == ast.LShift else "shr"
            return f"htmlk_{helper}_{resolved}({left}, {right})"
        if isinstance(item, ast.Compare):
            inferred_operand = require_pair(kind(item.left),
                                            kind(item.comparators[0]), "comparison")
            operand_type = inferred_operand if inferred_operand not in literals else (
                "i64" if inferred_operand == "negative_literal" else "u64"
            )
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

    output = emit(tree.body, expected_type)
    if type_out is not None:
        type_out.append(actual_type)
    return output
