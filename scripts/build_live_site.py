#!/usr/bin/env python3
"""Build one authentic HTML->C->HKEX->ROMFS native ISO for static Pages."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import tempfile
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

def build(out_dir: Path, *, source: Path | None = None) -> tuple[Path, Path]:
    selected = source if source is not None else APP
    if selected.is_symlink() or not selected.is_file():
        raise ValueError("source must be a regular, non-symlink HTML file")
    if out_dir.is_symlink():
        raise ValueError("refusing symlink output directory")
    out_dir.mkdir(parents=True, exist_ok=True)
    iso = out_dir / IMAGE
    manifest = out_dir / MANIFEST
    command = [sys.executable, str(ROOT / "scripts/build_boot.py"),
               "--source", str(KERNEL), "--romfs-run-console",
               "--exception-idt", "--tss-ist", "--user-fault-recover",
               "--out", str(iso), "--test-exit"]
    # Embed the *exact same* read-only HTML source bytes visible in Pages.
    # Do not mutate the shared examples/romfs tree or link through files from
    # outside this trusted source checkout. ROMFS validates size/path bounds.
    source_bytes = selected.read_bytes()
    if len(source_bytes) > 4096:
        raise ValueError("HTML source exceeds one bounded ROMFS file (4096 bytes)")
    with tempfile.TemporaryDirectory(prefix="htmlk-live-romfs-") as temp:
        romfs_root = Path(temp) / "romfs"
        shutil.copytree(ROOT / "examples/romfs", romfs_root, symlinks=True)
        (romfs_root / "source.html").write_bytes(source_bytes)
        # Compile the same immutable snapshot, not a possibly concurrently
        # edited working-tree file. ROMFS /source.html and HKEX stay in sync.
        source_snapshot = Path(temp) / "user-source.html"
        source_snapshot.write_bytes(source_bytes)
        subprocess.run([*command, "--romfs-root", str(romfs_root),
                        "--user-app-html", str(source_snapshot)], cwd=ROOT,
                       check=True)
    revision = os.environ.get("GITHUB_SHA", "")
    if len(revision) != 40 or any(c not in "0123456789abcdefABCDEF" for c in revision):
        revision = "local-build"
    metadata = {
        "kind": "html-kernel-os-native-boot",
        "image": IMAGE, "image_sha256": sha(iso),
        "image_bytes": iso.stat().st_size,
        "kernel_source": "examples/kernel.html",
        "kernel_source_sha256": sha(KERNEL),
        "user_source": ("examples/user-programs/html-u64-report.html"
                        if source is None else "local/" + selected.name),
        "user_source_sha256": hashlib.sha256(source_bytes).hexdigest(), "git_revision": revision,
        "embedded_source_path": "/source.html",
        "embedded_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "embedded_source_bytes": len(source_bytes),
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
    parser.add_argument("--source", type=Path, help="custom HTML-shaped user source:"
                        " compiled locally into the real native guest ISO")
    args = parser.parse_args()
    # Preserve final symlink identity so build() can reject symlink paths.
    build(args.out_dir.absolute(), source=args.source.absolute()
          if args.source is not None else None)

if __name__ == "__main__":
    main()
