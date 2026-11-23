#!/usr/bin/env python3
"""Check real HTML Kernel language files for humans or coding agents.

Examples:
  python3 scripts/htmlk_check.py examples/human-agent-hello.html --target user
  python3 scripts/htmlk_check.py - --target linux --format json < source.html

No output image or executable is created by this command.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compiler.diagnostics import check, diagnostic_from, describe  # noqa: E402
from compiler.language import MAX_SOURCE_BYTES  # noqa: E402


def read_source(path: str) -> str:
    if path == "-":
        data = sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1)
    else:
        file = Path(path)
        if file.is_symlink():
            raise ValueError("source cannot be a symlink")
        if not file.is_file():
            raise OSError("source is not an existing regular file")
        if file.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
        data = file.read_bytes()
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    return data.decode("utf-8", errors="strict")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="UTF-8 HTML Kernel source file; '-' reads stdin")
    parser.add_argument("--target", choices=("kernel", "linux", "user"), default="linux",
                        help="Check the same language for Linux, kernel, or native Ring3")
    parser.add_argument("--format", choices=("text", "json"), default="text",
                        help="Human error snippets or stable machine-readable JSON v1")
    parser.add_argument("--json", action="store_true", help="Alias for --format json")
    parser.add_argument("--describe", action="store_true",
                        help="Print supported tags/attributes/limits for humans or agents")
    args = parser.parse_args()
    fmt = "json" if args.json else args.format
    if args.describe:
        schema = describe()
        if fmt == "json":
            print(json.dumps(schema, ensure_ascii=False, sort_keys=True))
        else:
            print("HTML Kernel Language (strict HTML-shaped, native compiled subset)")
            print("Targets: " + ", ".join(schema["supported_targets"]))
            print("Example: " + schema["example"])
            for tag, entry in schema["tags"].items():
                print(f"  <{tag}> under {', '.join(entry['parents'])}; "
                      f"required {', '.join(entry['required_attributes']) or '(none)'}")
            print("Run --describe --json for all attributes, types and size limits.")
        return 0
    if args.input is None:
        parser.error("input is required unless --describe is supplied")
    source = ""
    try:
        source = read_source(args.input)
    except (OSError, UnicodeError, ValueError) as error:
        report = {
            "schema_version": 1, "ok": False, "file": args.input, "target": args.target,
            "source_sha256": None, "generated_c_sha256": None,
            "diagnostics": [asdict(diagnostic_from(error))],
        }
    else:
        report = check(source, target=args.target, file=args.input)
    if fmt == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    elif report["ok"]:
        print(f"OK {args.input} [{args.target}] — source valid; generated C checked in memory")
    else:
        for diagnostic in report["diagnostics"]:
            line = diagnostic["line"]
            column = diagnostic["column"]
            where = (f"{args.input}:{line}:{column}" if line is not None else args.input)
            print(f"{where}: error {diagnostic['code']}: {diagnostic['message']}",
                  file=sys.stderr)
            lines = source.splitlines()
            if line is not None and 1 <= line <= len(lines) and column is not None:
                text = lines[line-1]
                print(f"  {line:4d} | {text}", file=sys.stderr)
                print(f"       | {' ' * min(max(column - 1, 0), 200)}^", file=sys.stderr)
            if diagnostic["hint"]:
                print(f"  hint: {diagnostic['hint']}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
