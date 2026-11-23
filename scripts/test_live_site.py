#!/usr/bin/env python3
"""Independent exact published M5 user ISO -> actual QEMU COM1 acceptance."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML

APP = ROOT / 'examples/user-programs/html-u64-report.html'
KERNEL = ROOT / 'examples/kernel.html'
EXPECTED = (b'M5_C_USER_VALUE=4294967296\n'
            b'M5_C_USER_VALUE=4294967296\n'
            b'M5_C_USER_VALUE=18446744073709551615\n')

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(iso: Path, manifest: Path) -> None:
    data = json.loads(manifest.read_text(encoding='utf-8'))
    assert data['kind'] == 'html-kernel-os-native-boot'
    assert data['image'] == iso.name == 'html-kernel-live.iso'
    assert data['user_source'] == 'examples/user-programs/html-u64-report.html'
    assert data['user_timer'] is False
    assert data['test_exit'] is True
    assert data['image_sha256'] == sha(iso)
    assert data['image_bytes'] == iso.stat().st_size
    assert data['user_source_sha256'] == sha(APP)
    assert data['kernel_source_sha256'] == sha(KERNEL)
    # The HTML is inside the ISO ROMFS, not merely served as decorative web
    # content or stored in a detached repository asset. Bytes must match.
    assert data['embedded_source_path'] == '/source.html'
    source_bytes = APP.read_bytes()
    assert data['embedded_source_sha256'] == sha(APP)
    assert data['embedded_source_bytes'] == len(source_bytes)
    commands = [
        (b'help\r', b'M5_HELP help ls cat /path run /path exit'),
        (b'ls\r', b'M5_FILE /apps/hello.hke'),
        (b'cat /welcome.txt\r', b'Hello from a real embedded ROMFS!'),
        (b'cat /source.html\r', b'M5_CAT_END\n'),
        (b'run /missing.hke\r', b'M5_ERR_NOT_FOUND'),
        (b'run /apps/hello.hke\r', b'M5_RUN_EXIT_CODE=7\n'),
        (b'run /apps/hello.hke\r', b'M5_RUN_EXIT_CODE=7\n'),
        (b'exit\r', b'M5_CONSOLE_EXIT\n' + HTML),
    ]
    for attempt in range(2):
        trace, uart = exercise(iso, commands, HTML)
        expected_source = b'M5_CAT_BEGIN /source.html\n' + source_bytes + b'M5_CAT_END\n'
        assert trace.count(expected_source) == 1, (attempt, trace)
        assert uart.count(expected_source) == 1, (attempt, uart)
        assert trace.count(EXPECTED) == 2, (attempt, trace)
        assert uart.count(EXPECTED) == 2, (attempt, uart)
        assert trace.count(b'M5_C_RING3_EXIT_OK\n') == 2, trace
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n') == 2, trace
        assert trace.count(b'M5_RUN_EXIT_CODE=7\n') == 2, trace
        assert trace.count(b'M5_ERR_NOT_FOUND') == 1, trace
        assert b'M5_E2_X2APIC_TIMER_READY' not in trace
        print(f'LIVE PAGES ISO real QEMU {attempt+1}/2: help ls cat exact embedded HTML missing '
              'two HTML Ring3 programs, UINT64_MAX, cleanup, exit PASS', flush=True)
    print('LIVE PAGES EXACT IMAGE SHA256 / HTML SOURCE / CPU UART PASS')

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=ROOT/'build/live-site')
    args = parser.parse_args()
    verify(args.out_dir/'html-kernel-live.iso',
           args.out_dir/'html-kernel-live.json')

if __name__ == '__main__':
    main()
