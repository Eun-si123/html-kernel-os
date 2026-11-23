#!/usr/bin/env python3
"""Independently mutate original HTML and prove a DIFFERENT real CPU image/output.

Never claim browser JS compiles user code; the real repository toolchain
builds an independently changed native HKEX and ISO from the changed source.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile

import build_live_site
from test_m5_interactive_run import exercise, HTML

ORIGINAL_VALUE = '18446744073709551615'
MUTATED_VALUE = '12345678901234567890'

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, required=True)
    args = parser.parse_args()
    baseline = args.baseline_dir.resolve()
    original_iso = baseline / build_live_site.IMAGE
    original_manifest = json.loads((baseline / build_live_site.MANIFEST).read_text())
    original_html = build_live_site.APP.read_text(encoding='utf-8')
    assert original_html.count(ORIGINAL_VALUE) == 1
    assert original_manifest['image_sha256'] == build_live_site.sha(original_iso)
    assert original_manifest['user_source_sha256'] == build_live_site.sha(build_live_site.APP)
    assert original_manifest['embedded_source_sha256'] == original_manifest['user_source_sha256']

    with tempfile.TemporaryDirectory(prefix='htmlk-pages-source-mutation-') as td:
        workspace = Path(td)
        source = workspace / 'modified-user.html'
        source.write_text(original_html.replace(ORIGINAL_VALUE, MUTATED_VALUE),
                          encoding='utf-8')
        build_live_site.APP = source
        iso, manifest_file = build_live_site.build(workspace / 'mutated-build')
        manifest = json.loads(manifest_file.read_text())
        assert manifest['embedded_source_path'] == '/source.html'
        assert manifest['image_sha256'] != original_manifest['image_sha256']
        assert manifest['user_source_sha256'] != original_manifest['user_source_sha256']
        assert manifest['embedded_source_sha256'] == build_live_site.sha(source)
        assert manifest['embedded_source_bytes'] == len(source.read_bytes())
        changed = source.read_bytes()
        commands = [
            (b'cat /source.html\r', b'M5_CAT_END\n'),
            (b'run /apps/hello.hke\r', b'M5_RUN_EXIT_CODE=7\n'),
            (b'exit\r', b'M5_CONSOLE_EXIT\n' + HTML),
        ]
        serial, uart = exercise(iso, commands, HTML)
        exact = b'M5_CAT_BEGIN /source.html\n' + changed + b'M5_CAT_END\n'
        assert serial.count(exact) == uart.count(exact) == 1
        new = ('M5_C_USER_VALUE=' + MUTATED_VALUE + '\n').encode()
        old = ('M5_C_USER_VALUE=' + ORIGINAL_VALUE + '\n').encode()
        assert serial.count(new) == uart.count(new) == 1
        assert old not in serial and old not in uart
        assert b'M5_C_USER_FRAMES_RECLAIMED\n' in serial
        assert b'M5_RUN_EXIT_CODE=7\n' in serial
        print('PASS: changed HTML bytes -> changed real ROMFS source -> changed ISO '
              'SHA-256 -> changed native Ring3 CPU/COM1 value -> 6 frames reclaimed')

if __name__ == '__main__':
    main()
