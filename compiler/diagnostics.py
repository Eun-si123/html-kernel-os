"""Stable, machine-readable diagnostics for the existing HTML Kernel compiler.

This is a presentation layer only: it never reparses or relaxes the
language grammar. compile_html remains the single authoritative validator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import get_close_matches
from hashlib import sha256
import re
from typing import Any

from .htmlk import compile_html
from .language import (
    ALLOWED, CHILDREN, REQUIRED, INT_TYPES, CompileError, MAX_SOURCE_BYTES,
    MAX_NODES, MAX_RUNTIME_STEPS, MAX_LOOP_TIMES, MAX_ARRAY_LENGTH,
    MAX_ARRAY_DECLS, MAX_FUNCTIONS, MAX_FUNCTION_ARGS, MAX_FUNCTION_DEPTH,
    MAX_OUTPUT_BYTES,
)

LOCATION = re.compile(r"^line (?P<line>[0-9]+), column (?P<column>[0-9]+): (?P<message>.*)$", re.S)
BAD_TAG = re.compile(r"<([a-z][a-z0-9_-]*)> is not allowed under ")
BAD_ATTRS = re.compile(r"invalid attributes on <([a-z][a-z0-9_-]*)>")


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    line: int | None
    column: int | None
    hint: str | None


def hint_for(message: str) -> tuple[str, str | None]:
    tag = BAD_TAG.search(message)
    if tag:
        name = tag.group(1)
        close = get_close_matches(name, sorted(CHILDREN), n=1, cutoff=0.65)
        hint = (f"Did you mean <{close[0]}>?" if close else
                "Use only documented HTML Kernel tags and valid parent elements.")
        return "HK101_TAG", hint
    attrs = BAD_ATTRS.search(message)
    if attrs:
        allowed = ", ".join(sorted(ALLOWED.get(attrs.group(1), set())))
        return "HK102_ATTRS", (f"Allowed attributes: {allowed or '(none)'}. "
                              "Use documented names and quoted values; value semantics are target-specific.")
    if "unexpected closing tag" in message or "expected closed" in message:
        return "HK103_NESTING", "Close each tag in reverse opening order; use <halt/> for empty tags."
    if "only supported" in message and "arch" in message:
        return "HK104_ARCH", 'Start with <kernel arch="x86_64">.'
    if "user target requires" in message or "user output" in message:
        return "HK210_USER_TARGET", (
            "Ring3 user programs need a final unconditional <print> followed by <halt/>; "
            "at most eight report syscalls.")
    if "halt code is only valid" in message:
        return "HK211_TARGET", 'Use <halt/> on kernel/Linux or --target user for <halt code="7"/>.'
    if "source exceeds" in message or "too many" in message or "exceeds" in message:
        return "HK301_BOUNDS", "Reduce input size, nesting, loop count, or static output budget."
    if "invalid expression" in message:
        return "HK201_EXPR", ('Use a typed expression in quotes; write HTML &lt; for "<" '
                              'inside an attribute.')
    if "name" in message or "type" in message:
        return "HK202_TYPE", "Use declared ASCII names with explicit u32/u64/i32/i64 types."
    if "text is only allowed" in message:
        return "HK105_TEXT", 'Place printable text inside <print>...</print>.'
    return "HK100_COMPILE", None


def diagnostic_from(error: Exception) -> Diagnostic:
    message = str(error)
    line = column = None
    matched = LOCATION.fullmatch(message)
    if matched:
        line = int(matched.group("line"))
        column = int(matched.group("column"))
        message = matched.group("message")
    code, hint = hint_for(message)
    if isinstance(error, UnicodeError):
        code, hint = "HK002_UTF8", "Save the file as valid UTF-8 without replacing invalid bytes."
    elif isinstance(error, OSError):
        code, hint = "HK003_FILE", "Confirm the input file exists and is readable."
    return Diagnostic("error", code, message, line, column, hint)


def check(source: str, *, target: str, file: str) -> dict[str, Any]:
    data = source.encode("utf-8")
    result: dict[str, Any] = {
        "schema_version": 1, "ok": False, "file": file,
        "target": target, "source_sha256": sha256(data).hexdigest(),
        "diagnostics": [], "generated_c_sha256": None,
    }
    try:
        if len(data) > MAX_SOURCE_BYTES:
            raise CompileError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
        c = compile_html(source, target=target)
    except (CompileError, UnicodeError, ValueError) as error:
        result["diagnostics"] = [asdict(diagnostic_from(error))]
        return result
    result["ok"] = True
    result["generated_c_sha256"] = sha256(c.encode("utf-8")).hexdigest()
    return result


def describe() -> dict[str, Any]:
    """Agent-readable supported grammar assembled from canonical tables.

    This is a discoverable SUBSET declaration, not a general HTML or LSP
    language-server specification; semantic constraints remain in compiler.
    """
    return {
        "schema_version": 1, "dialect": "HTML Kernel Language",
        "syntax": "strict HTML-shaped, not browser/DOM HTML",
        "supported_targets": ["kernel", "linux", "user"],
        "entrypoint": '<kernel arch="x86_64"><onboot>...</onboot></kernel>',
        "tags": {
            tag: {
                "parents": sorted(
                    {"(document)" if parent is None else parent for parent in parents}
                    | ({"main"} if "onboot" in parents else set())
                ),  # actual validated <main> alias uses the same onboot AST
                "attributes": sorted(ALLOWED[tag]),
                "required_attributes": sorted(REQUIRED.get(tag, set())),
            }
            for tag, parents in sorted(CHILDREN.items())
        },
        "types": sorted(INT_TYPES),
        "limits": {
            "source_bytes": MAX_SOURCE_BYTES, "ast_nodes": MAX_NODES,
            "estimated_steps": MAX_RUNTIME_STEPS,
            "estimated_output_bytes": MAX_OUTPUT_BYTES,
            "loop_max": MAX_LOOP_TIMES, "array_length": MAX_ARRAY_LENGTH,
            "array_declarations": MAX_ARRAY_DECLS,
            "functions": MAX_FUNCTIONS, "function_parameters": MAX_FUNCTION_ARGS,
            "function_depth": MAX_FUNCTION_DEPTH,
        },
        "notes": [
            "Use quoted attribute expressions and HTML &lt; for < in conditions.",
            "Native Ring3 user output is bounded and requires a final print then halt.",
            "Only supported tags and attributes compile; no DOM scripting, JS, or browser HTML semantics.",
            "For native Linux/Ring3 apps, <program><main> aliases <kernel><onboot> with identical typed semantics; kernel target requires <kernel>.",
            "Check source with scripts/htmlk_check.py before building a native artifact.",
        ],
        "example": "examples/human-agent-hello.html",
    }
