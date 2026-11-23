#!/usr/bin/env python3
"""M5-F1: shared HTML-like compiler -> relocation-free native CPL3 HKEX."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import tempfile
import sys

from build_user_image import MAX_CODE_BYTES, pack

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from compiler.htmlk import compile_html  # noqa: E402


def run(*args: str | Path) -> str:
    result = subprocess.run([str(arg) for arg in args], capture_output=True,
                            text=True, timeout=30, check=True)
    return result.stdout


def build(source: Path, output: Path) -> bytes:
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 131072:
        raise ValueError("user HTML source must be a real regular file <=128 KiB")
    c_text = compile_html(source.read_text(encoding="utf-8"), target="user")
    with tempfile.TemporaryDirectory(prefix="htmlk-html-user-") as root:
        directory = Path(root)
        generated = directory / "user.c"
        generated.write_text(c_text, encoding="utf-8")
        object_file = directory / "user.o"
        entry = directory / "entry.o"
        executable = directory / "user.elf"
        raw = directory / "user.raw"
        run('gcc', '-std=c11', '-Os', '-march=x86-64', '-mtune=generic',
            '-fno-pie', '-fno-pic', '-fno-plt', '-ffreestanding',
            '-fno-builtin', '-fno-stack-protector', '-fno-asynchronous-unwind-tables',
            '-fno-unwind-tables', '-fno-jump-tables', '-fno-common',
            '-fcf-protection=none', '-mno-red-zone', '-mgeneral-regs-only',
            '-ffunction-sections', '-fdata-sections', '-Wall', '-Wextra',
            '-Werror', '-c', generated, '-o', object_file)
        run('gcc', '-c', '-m64', '-fno-pie', '-fno-pic',
            ROOT/'scripts/user_program_entry.S', '-o', entry)
        run('ld', '-m', 'elf_x86_64', '-nostdlib', '--gc-sections',
            '-T', ROOT/'scripts/user_program.ld', '-o', executable,
            entry, object_file)
        section_info = run('readelf', '-WS', executable)
        allocated = []
        for line in section_info.splitlines():
            fields = line.replace('[', ' ').replace(']', ' ').split()
            if len(fields) >= 9 and fields[0].isdigit() and fields[2] in (
                'PROGBITS', 'NOBITS') and 'A' in fields[7]:
                allocated.append(fields[1])
        if allocated != ['.text']:
            raise ValueError(f"HKEX requires only executable .text: {allocated}")
        relocations = run('readelf', '-r', '-W', executable)
        if 'There are no relocations in this file.' not in relocations:
            raise ValueError("HKEX user image retains relocations")
        run('objcopy', '--only-section=.text', '-O', 'binary', executable, raw)
        code = raw.read_bytes()
        if not 0 < len(code) <= MAX_CODE_BYTES:
            raise ValueError(f"HKEX user code must be 1..{MAX_CODE_BYTES} bytes")
        image = pack(code)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        image = build(args.source, args.out)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    print(f'HKEX_HTML_USER_IMAGE_BYTES={len(image)}')


if __name__ == '__main__':
    main()
