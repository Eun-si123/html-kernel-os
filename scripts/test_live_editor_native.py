#!/usr/bin/env python3
"""Live editor's EXACT downloadable template -> native compile -> BIOS QEMU Ring3.

No JavaScript output emulator: original and edited source both get truly
compiled into new native BIOS ISOs and observed through real guest COM1.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML

EDITOR_MODULE = ROOT / 'site/live/editor.mjs'
VALUE = '2026'
CHANGED = '2031'


def source_template() -> bytes:
    js = ('import { TEMPLATE } from ' + json.dumps(EDITOR_MODULE.as_uri()) +
          '; process.stdout.write(TEMPLATE);')
    result = subprocess.run(['node', '--input-type=module', '-e', js],
                            capture_output=True, check=True, timeout=8)
    return result.stdout


def build_image(source: Path, out: Path) -> tuple[Path, dict]:
    result = subprocess.run([sys.executable, str(ROOT/'scripts/build_live_site.py'),
                             '--source', str(source), '--out-dir', str(out)],
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (result.stdout[-2500:], result.stderr[-1800:])
    manifest = json.loads((out/'html-kernel-live.json').read_text())
    iso = out/'html-kernel-live.iso'
    assert manifest['user_source'] == 'local/' + source.name
    assert manifest['embedded_source_path'] == '/source.html'
    assert manifest['embedded_source_bytes'] == len(source.read_bytes())
    assert manifest['embedded_source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest['image_sha256'] == hashlib.sha256(iso.read_bytes()).hexdigest()
    assert 'expected_marker' not in manifest, 'custom source cannot inherit default exit7'
    return iso, manifest


def boot_source(iso: Path, source: bytes, value: str) -> None:
    trace, uart = exercise(iso, [
        (b'cat /source.html\r', b'M5_CAT_END\n'),
        (b'run /apps/hello.hke\r', b'M5_RUN_DONE\n'),
        (b'exit\r', b'M5_CONSOLE_EXIT\n'+HTML),
    ], HTML)
    raw = b'M5_CAT_BEGIN /source.html\n'+source+b'M5_CAT_END\n'
    assert trace.count(raw) == uart.count(raw) == 1
    payload = ('M5_C_USER_VALUE='+value+'\n').encode()
    assert trace.count(payload) == uart.count(payload) == 1
    assert b'M5_C_USER_FRAMES_RECLAIMED\n' in trace
    assert b'M5_ERR_USER_SYSCALL' not in trace


def main() -> None:
    template = source_template()
    assert 0 < len(template) <= 4096
    assert template.count(VALUE.encode()) == 1
    with tempfile.TemporaryDirectory(prefix='htmlk-live-editor-genuine-') as td:
        root = Path(td)
        original = root/'htmlk-program.html'
        original.write_bytes(template)
        base_iso, _ = build_image(original, root/'original')
        boot_source(base_iso, template, VALUE)
        print('M2-UX4 browser editor exact source bytes -> native ISO -> '
              'real QEMU ROMFS/CPU 2026 and frame reclaim PASS', flush=True)

        edited_bytes = template.replace(VALUE.encode(), CHANGED.encode())
        edited = root/'modified.html'
        edited.write_bytes(edited_bytes)
        new_iso, _ = build_image(edited, root/'changed')
        assert base_iso.read_bytes() != new_iso.read_bytes()
        boot_source(new_iso, edited_bytes, CHANGED)
        print('M2-UX4 browser editor changed source -> changed ISO -> '
              'genuine CPU 2031, raw guest ROMFS source and reclaim PASS')


if __name__ == '__main__':
    main()
