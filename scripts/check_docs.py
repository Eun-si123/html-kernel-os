#!/usr/bin/env python3
"""Check local Markdown links in canonical public documentation (no network)."""
from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    "README.md", "AGENTS.md", "CODEMAP.md", "CLAUDE.md",
    ".github/copilot-instructions.md",
    "docs/README.md", "docs/STATUS.md", "docs/VALIDATION.md",
    "docs/ARCHITECTURE.md", "docs/DECISIONS.md",
    "docs/AGENT_GOVERNANCE.md", "docs/AGENT_WORK_QUEUE.md",
    "docs/AGENT_MEMORY.md", "docs/AGENT_COMMIT_IDENTITY.md",
    "agent-evals/README.md",
]
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
REMOTE = ("http:", "https:", "mailto:", "tel:", "data:")


def local_links(markdown: str) -> list[str]:
    in_fence = False
    fence_char = ""
    fence_len = 0
    found = []
    for line in markdown.splitlines():
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                in_fence = False
            continue
        if in_fence:
            continue
        found.extend(m.group(1).split(' "')[0] for m in LINK.finditer(line))
    return found


def validate_file(root: Path, rel: str) -> list[str]:
    doc = root / rel
    if not doc.is_file():
        return [f"{rel}: missing documentation file"]
    errors = []
    for link in local_links(doc.read_text(encoding="utf-8")):
        if not link or link.startswith(("#", "//")) or link.startswith(REMOTE):
            continue
        path = unquote(urlsplit(link).path)
        if not path:
            continue
        target = (doc.parent / path).resolve()
        if not target.is_relative_to(root.resolve()) or not target.exists():
            errors.append(f"{rel}: invalid local link {link}")
    return errors


def main() -> int:
    errors = []
    for name in DOCS:
        errors.extend(validate_file(ROOT, name))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"Documentation links FAILED: {len(errors)} errors", file=sys.stderr)
        return 1
    print(f"Documentation links OK: {len(DOCS)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
