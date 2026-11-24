#!/usr/bin/env python3
"""Publish exact compiler-derived grammar metadata for static GitHub Pages.

No browser-side grammar parser/compiler is created; this JSON is read-only.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compiler.diagnostics import describe  # noqa: E402


def generate() -> dict:
    grammar = describe()
    grammar["compiler_source_sha256"] = {
        file: sha256((ROOT/file).read_bytes()).hexdigest()
        for file in ("compiler/language.py", "compiler/htmlk.py")
    }
    grammar["distribution"] = "read-only compiler-derived public grammar metadata"
    return grammar


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    path = args.out
    if path.is_symlink():
        raise ValueError("refusing symlink metadata destination")
    if not path.parent.is_dir():
        raise FileNotFoundError("metadata output directory must already exist")
    payload = json.dumps(generate(), ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')) + '\n'
    if len(payload.encode('utf-8')) > 16384:
        raise ValueError("public grammar exceeds 16 KiB")
    path.write_text(payload, encoding='utf-8')
    print('HTMLK_PUBLIC_GRAMMAR_BYTES=' + str(len(payload.encode('utf-8'))))


if __name__ == '__main__':
    main()
