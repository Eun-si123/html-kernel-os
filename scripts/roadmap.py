#!/usr/bin/env python3
"""Read-only Markdown roadmap gate reader for humans and coding agents.

Produces a concise plan, not a task lease, feature completion claim or CI result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs" / "ROADMAP.md"
ROW = re.compile(r"^\|\s*\*\*(M\d+)(\s+—\s+NEXT)?\*\*\s*\|")
REFERENCE = re.compile(r"\bM\d+\b")


def parse_roadmap(text: str) -> dict:
    milestones = []
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            raise ValueError("roadmap milestone must have 4 table columns")
        mid, name, dependencies, gate = cells
        ident = match.group(1)
        if not ident or not name or len(gate) < 20:
            raise ValueError(f"{ident}: missing goal or acceptance gate")
        deps = sorted(set(REFERENCE.findall(dependencies)))
        if len(deps) != len(REFERENCE.findall(dependencies)):
            raise ValueError(f"{ident}: duplicate dependencies")
        milestones.append({
            "id": ident,
            "goal": name.replace("**", ""),
            "dependsOn": deps,
            "acceptanceGate": gate,
            "markedNext": bool(match.group(2)),
        })
    if len(milestones) < 2:
        raise ValueError("missing milestone rows")
    seen = set()
    for idx, step in enumerate(milestones):
        ident = step["id"]
        if ident in seen or ident != f"M{idx}":
            raise ValueError("milestones must be unique sequential IDs starting M0")
        for dep in step["dependsOn"]:
            if dep not in seen:
                raise ValueError(f"{ident}: unknown or forward dependency: {dep}")
        seen.add(ident)
    nexts = [m["id"] for m in milestones if m["markedNext"]]
    if len(nexts) != 1:
        raise ValueError("roadmap must identify exactly one NEXT gate")
    next_id = nexts[0]
    if next_id == "M0":
        raise ValueError("M0 baseline cannot be marked NEXT")
    return {
        "schemaVersion": 1,
        "nextSuggested": next_id,
        "milestones": milestones,
        "limitation": "This is a plan and dependencies, not measured progress; inspect docs/STATUS.md, source, Issues, PRs and CI.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="validate milestone table")
    group.add_argument("--json", action="store_true", help="emit read-only structured roadmap")
    args = parser.parse_args()
    try:
        report = parse_roadmap(ROADMAP.read_text(encoding="utf-8"))
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"Roadmap valid: {len(report['milestones'])} milestones; "
                  f"suggested NEXT={report['nextSuggested']} (not a completion assertion)")
        return 0
    except (OSError, ValueError) as exc:
        print("roadmap validation FAILED:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
