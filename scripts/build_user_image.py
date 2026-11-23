#!/usr/bin/env python3
"""Build bounded relocation-free x86-64 code into the M5-C1 HKEX format."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

HEADER_BYTES = 32
MAX_CODE_BYTES = 4096 - HEADER_BYTES


def fnv1a(data: bytes) -> int:
    digest = 2166136261
    for byte in data:
        digest = ((digest ^ byte) * 16777619) & 0xffffffff
    return digest


def pack(code: bytes) -> bytes:
    if not 0 < len(code) <= MAX_CODE_BYTES:
        raise ValueError(f"HKEX code length must be 1..{MAX_CODE_BYTES}")
    return (b'HKEX' + bytes([1, HEADER_BYTES, 0, 0]) +
            (0).to_bytes(4, 'little') + len(code).to_bytes(4, 'little') +
            fnv1a(code).to_bytes(4, 'little') + bytes(12) + code)


def build(source: Path, output: Path) -> bytes:
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"HKEX source must be a regular assembly file: {source}")
    if source.stat().st_size > 16384:
        raise ValueError("HKEX assembly source size exceeds 16 KiB")
    with tempfile.TemporaryDirectory(prefix="htmlk-hke-") as temp:
        obj = Path(temp) / "user.o"
        raw = Path(temp) / "user.bin"
        subprocess.run(["gcc", "-m64", "-c", "-fno-pic", "-fno-pie",
                        "-o", str(obj), str(source.resolve())],
                       check=True, timeout=30)
        sections = subprocess.run(["readelf", "-W", "-r", str(obj)],
                                  capture_output=True, text=True, check=True,
                                  timeout=20).stdout
        if re.search(r'\b[0-9a-fA-F]{8,16}\s+[0-9a-fA-F]{8,16}\s+', sections):
            raise ValueError("HKEX programs must be relocation-free")
        subprocess.run(["objcopy", "--only-section=.text", "-O", "binary",
                        str(obj), str(raw)], check=True, timeout=20)
        if not raw.is_file() or raw.stat().st_size > MAX_CODE_BYTES:
            raise ValueError("HKEX .text image too large")
        image = pack(raw.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    return image


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    image = build(args.source, args.out)
    print(f'HKEX_IMAGE_BYTES={len(image)} HKEX_CODE_FNV1A={fnv1a(image[32:]):08x}')
