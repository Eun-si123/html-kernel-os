#!/usr/bin/env python3
"""Build one authentic HTML->C->HKEX->ROMFS native ISO for static Pages."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "examples/kernel.html"
APP = ROOT / "examples/user-programs/html-u64-report.html"
IMAGE = "html-kernel-live.iso"
MANIFEST = "html-kernel-live.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(out_dir: Path) -> tuple[Path, Path]:
    if out_dir.is_symlink():
        raise ValueError("refusing symlink output directory")
    out_dir.mkdir(parents=True, exist_ok=True)
    iso = out_dir / IMAGE
    manifest = out_dir / MANIFEST
    command = [sys.executable, str(ROOT / "scripts/build_boot.py"),
               "--source", str(KERNEL), "--romfs-run-console",
               "--exception-idt", "--tss-ist", "--user-fault-recover",
               "--user-app-html", str(APP),
               "--out", str(iso), "--test-exit"]
    subprocess.run(command, cwd=ROOT, check=True)
    revision = os.environ.get("GITHUB_SHA", "")
    if len(revision) != 40 or any(c not in "0123456789abcdefABCDEF" for c in revision):
        revision = "local-build"
    metadata = {
        "kind": "html-kernel-os-native-boot",
        "image": IMAGE, "image_sha256": sha(iso),
        "image_bytes": iso.stat().st_size,
        "kernel_source": "examples/kernel.html",
        "kernel_source_sha256": sha(KERNEL),
        "user_source": "examples/user-programs/html-u64-report.html",
        "user_source_sha256": sha(APP), "git_revision": revision,
        "user_timer": False, "test_exit": True,
        "user_command": "run /apps/hello.hke",
        "expected_marker": "M5_RUN_EXIT_CODE=7",
    }
    manifest.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("HTMLK_LIVE_ISO_SHA256=" + metadata["image_sha256"])
    return iso, manifest

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build/live-site")
    args = parser.parse_args()
    build(args.out_dir.resolve())

if __name__ == "__main__":
    main()
