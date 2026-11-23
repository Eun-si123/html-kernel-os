#!/usr/bin/env python3
"""Deterministically turn a tiny trusted directory into kernel .rodata; never host-run files."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

MAX_FILES = 16
MAX_FILE_BYTES = 4096
MAX_TOTAL_BYTES = 32768
MAX_PATH = 63


def valid_path(path: str) -> bool:
    return (path.startswith("/") and len(path) <= MAX_PATH and
            all(part and part not in (".", "..") and
                all(char.isascii() and (char.isalnum() or char in "._-")
                    for char in part) for part in path[1:].split("/")))


def collect(root: Path) -> list[tuple[str, bytes]]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("ROMFS root must be a regular directory")
    result: list[tuple[str, bytes]] = []
    total = 0
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise ValueError(f"ROMFS symlink rejected: {candidate}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"ROMFS special file rejected: {candidate}")
        path = "/" + candidate.relative_to(root).as_posix()
        if not valid_path(path):
            raise ValueError(f"noncanonical ROMFS path rejected: {path}")
        if len(result) == MAX_FILES or candidate.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("ROMFS file count or size limit exceeded")
        # Limit bytes read even if the file grows after stat() or is swapped.
        # Inputs are trusted local build assets, never downloaded on boot.
        with candidate.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
            raise ValueError("ROMFS byte limit exceeded")
        total += len(data)
        result.append((path, data))
    if not result:
        raise ValueError("ROMFS cannot be empty")
    return sorted(result)


def generate(root: Path, destination: Path) -> str:
    files = collect(root)
    digest = hashlib.sha256()
    lines = ['/* Generated from bounded ROMFS source files; do not edit. */',
             '#include "romfs.h"']
    for index, (path, data) in enumerate(files):
        digest.update(path.encode("ascii") + b"\0" + len(data).to_bytes(4, "little") + data)
        if data:
            lines.append(f'static const uint8_t blob_{index}[] = {{')
            for off in range(0, len(data), 16):
                lines.append('    ' + ', '.join(f'0x{b:02x}' for b in data[off:off+16]) + ',')
            lines.append('};')
    lines.append('static const struct htmlk_romfs_file files[] = {')
    for index, (path, data) in enumerate(files):
        blob = f'blob_{index}' if data else '0'
        lines.append(f'    {{"{path}", {blob}, {len(data)}U}},')
    lines.extend(['};', 'const struct htmlk_romfs_volume htmlk_romfs_image =',
                  '    { files, sizeof(files)/sizeof(files[0]) };', ''])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="ascii")
    return digest.hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print('ROMFS_CONTENT_SHA256=' + generate(args.root, args.out))
