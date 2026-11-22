#!/usr/bin/env python3
"""Fetch browser x86-64 emulator assets with pinned content hashes."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
from urllib.request import urlopen

BASE = "https://portlandhodl.github.io/v86_64/"
# Reviewed 2026-11-22. Browser binaries are not checked into the source repo.
ASSETS = {
    "v86_all.js": ("build/v86_all.js", "d84c4279325bc3f4084dad32f985bce60809ae7c49f780d81e63ac96f7e8947c"),
    "v86.wasm": ("build/v86.wasm", "fc9e655c68eaf8aed50ccf987897bfb211ae793832b498a6d9c6a4733618ad2b"),
    "seabios.bin": ("bios/seabios.bin", "73e3f359102e3a9982c35fce98eb7cd08f18303ac7f1ba6ebfbe6cdc1c244d98"),
    "vgabios.bin": ("bios/vgabios.bin", "a4bc0d80cc3ca028c73dafa8fee396b8d054ce87ebd8abfbd31b06b437607880"),
}
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--cache-dir", type=Path, default=Path(os.environ.get(
        "HTMLK_CACHE_DIR", "build/.cache")) / "browser")
    args = ap.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    for name, (remote, expected) in ASSETS.items():
        cached = args.cache_dir / name
        if not cached.exists():
            with urlopen(BASE + remote, timeout=40) as response:
                data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise RuntimeError("download too large: " + name)
            cached.write_bytes(data)
        actual = hashlib.sha256(cached.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"{name}: checksum mismatch {actual} != {expected}")
        shutil.copy2(cached, args.dest / name)
        print(f"PINNED {name} sha256={actual}")
    print("All browser emulator assets verified and copied")


if __name__ == "__main__":
    main()
