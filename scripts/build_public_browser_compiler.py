#!/usr/bin/env python3
"""Copy the actual Python HTMLK compiler and a hash manifest for browser WASM.

Only the six explicitly listed public-safe Python modules are exported.
The worker loads these unchanged bytes in Pyodide's private virtual FS.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
COMPILER_FILES = ('__init__.py', 'numeric_types.py', 'language.py',
                  'function_codegen.py', 'htmlk.py', 'diagnostics.py')
MAX_COMPILER_FILE = 100_000


def build(directory: Path) -> dict:
    if directory.is_symlink():
        raise ValueError('refusing browser compiler symlink output directory')
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'runtime': 'Pyodide', 'pyodide_version': '0.29.5',
                'compiler': 'HTML Kernel Language canonical Python compiler',
                'target': 'user', 'files': {}}
    for name in COMPILER_FILES:
        source = ROOT / 'compiler' / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('missing or symlinked canonical compiler: ' + name)
        raw = source.read_bytes()
        if len(raw) > MAX_COMPILER_FILE:
            raise ValueError('oversize canonical compiler: ' + name)
        destination = directory / name
        if destination.is_symlink():
            raise ValueError('refusing symlink destination: ' + name)
        destination.write_bytes(raw)
        manifest['files'][name] = {'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}
    output = directory / 'manifest.json'
    if output.is_symlink():
        raise ValueError('refusing manifest symlink destination')
    output.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                 separators=(',', ':')) + '\n', encoding='utf-8')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    manifest = build(args.out_dir)
    print('HTMLK_BROWSER_COMPILER_FILES=' + str(len(manifest['files'])))


if __name__ == '__main__':
    main()
