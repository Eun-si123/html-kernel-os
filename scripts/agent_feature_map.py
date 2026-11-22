#!/usr/bin/env python3
"""Read-only feature-to-regression routing, compatible with BetterNet-App practice.

A mapping report is advisory; no tests or native kernels are executed by impact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "agent-evals" / "feature-contracts.json"
FEATURE_ID = re.compile(r"^[a-z][a-z0-9-]{1,60}$")
GIT_REF = re.compile(r"^[A-Za-z0-9_./-]{1,100}$")
PRODUCTION_PATHS = ("compiler/", "site/")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def safe_file(root: Path, path: str) -> Path:
    require(isinstance(path, str) and bool(path) and
            not path.startswith(("/", "-")) and
            "\\" not in path and
            "." not in path.split("/") and
            ".." not in path.split("/"), "unsafe repository-relative file path")
    target = (root / path).resolve()
    require(target.is_relative_to(root.resolve()),
            f"out-of-root path: {path}")
    require(target.is_file(), f"missing file: {path}")
    return target


def validate(document: dict, root: Path = ROOT) -> list[dict]:
    require(isinstance(document, dict) and
            document.get("schemaVersion") == 1, "schemaVersion must be 1")
    items = document.get("features")
    require(isinstance(items, list) and bool(items), "nonempty features required")
    seen: set[str] = set()
    for entry in items:
        require(isinstance(entry, dict), "invalid feature entry")
        fid = entry.get("id")
        require(isinstance(fid, str) and bool(FEATURE_ID.fullmatch(fid)) and
                fid not in seen, "duplicate/invalid feature ID")
        seen.add(fid)
        for field in ("source", "regressions", "fieldEvidence"):
            paths = entry.get(field)
            require(isinstance(paths, list) and bool(paths), f"{fid}: missing {field}")
            require(len(paths) == len(set(p for p in paths if isinstance(p, str))) and
                    all(isinstance(p, str) for p in paths), f"{fid}: duplicate/invalid {field}")
            for path in paths:
                safe_file(root, path)
        require(all(p.startswith("tests/") and p.endswith(".py") for p in entry["regressions"]),
                f"{fid}: regressions must be runnable Python tests")
        require(not (set(entry["source"]) & set(entry["regressions"])),
                f"{fid}: source/tests overlap")
    return items


def summarize(features: list[dict], changed: list[str]) -> dict:
    paths = set(changed)
    affected = []
    mapped = set()
    for feature in features:
        source = sorted(set(feature["source"]) & paths)
        mapped.update(feature["source"])
        if not source:
            continue
        edited_tests = sorted(set(feature["regressions"]) & paths)
        affected.append({
            "feature": feature["id"],
            "changedSource": source,
            "existingRegressionTests": feature["regressions"],
            "changedRegressionTests": edited_tests,
            "fieldEvidence": feature["fieldEvidence"],
            "review": ("regression-test-change-present" if edited_tests
                       else "review-existing-regressions-for-new-behavior"),
            "automatedEvidence": "not-run",
            "fieldStatus": "not-run",
        })
    return {
        "schemaVersion": 1,
        "changedFiles": sorted(paths),
        "affectedFeatures": affected,
        "unmappedSourceFiles": sorted(p for p in paths if
                                      p.startswith(PRODUCTION_PATHS) and
                                      p not in mapped and p.endswith((".py", ".js", ".css", ".html"))),
        "limitation": "Mapping paths recommends reviews only; it does not execute tests or boot an OS.",
    }


def git_diff(base: str, head: str, root: Path = ROOT) -> list[str]:
    require(all(isinstance(ref, str) and bool(GIT_REF.fullmatch(ref))
                and not ref.startswith(("-", "/")) and ".." not in ref
                for ref in (base, head)), "invalid Git reference")
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", "--no-ext-diff",
         f"{base}...{head}", "--"],
        cwd=root, capture_output=True, timeout=20, check=False,
    )
    require(result.returncode == 0, "Git diff unavailable (check refs and repository access)")
    return [p.decode("utf-8") for p in result.stdout.split(b"\0") if p]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "impact"))
    parser.add_argument("--base", help="Git base SHA/ref")
    parser.add_argument("--head", help="Git head SHA/ref")
    args = parser.parse_args()
    try:
        features = validate(json.loads(MAP.read_text(encoding="utf-8")))
        if args.action == "validate":
            print(f"Feature contracts verified: {len(features)} features")
        else:
            require(bool(args.base) and bool(args.head),
                    "impact requires --base and --head")
            print(json.dumps(summarize(features, git_diff(args.base, args.head)),
                             indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print("agent-feature-map: validation failed:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
