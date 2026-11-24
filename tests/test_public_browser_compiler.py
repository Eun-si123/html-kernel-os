"""Browser Pyodide files are byte-exact canonical Python compiler sources.

Real Chromium Worker parity is an independent (not mocked) browser test;
this test protects the shipped Pages provenance and native compiler contract.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compiler.diagnostics import check
from compiler.htmlk import compile_html
from scripts.build_public_browser_compiler import COMPILER_FILES, ROOT, build


class BrowserCompilerTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_contains_exact_canonical_sources(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)/'compiler'
            old = build(directory)
            before = (directory/'manifest.json').read_bytes()
            self.assertEqual(old, build(directory))
            self.assertEqual(before, (directory/'manifest.json').read_bytes())
            self.assertEqual(old['pyodide_version'],'0.29.5')
            self.assertEqual(old['target'],'user')
            self.assertEqual(len(old['files']),6)
            self.assertEqual(set(old['files']),set(COMPILER_FILES))
            for name in COMPILER_FILES:
                expected=(ROOT/'compiler'/name).read_bytes()
                actual=(directory/name).read_bytes()
                self.assertEqual(actual,expected)
                self.assertEqual(old['files'][name]['sha256'],hashlib.sha256(expected).hexdigest())
                self.assertEqual(old['files'][name]['bytes'],len(expected))

    def test_symlink_destinations_are_never_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            victim=root/'victim.txt'
            victim.write_text('NEVER REPLACE')
            output=root/'safe'
            output.mkdir()
            (output/'language.py').symlink_to(victim)
            with self.assertRaises(ValueError):
                build(output)
            self.assertEqual(victim.read_text(),'NEVER REPLACE')
            bad_dir=root/'outside'
            bad_dir.symlink_to(output)
            with self.assertRaises(ValueError):
                build(bad_dir)

    def test_user_program_differential_code_hash_and_errors(self):
        template=subprocess.check_output(['node','--input-type=module','-e',
                   'import {TEMPLATE} from "./site/live/editor.mjs"; process.stdout.write(TEMPLATE)'],
                   cwd=ROOT,timeout=8).decode()
        changed=template.replace('value="2026"','value="2031"')
        self.assertNotEqual(template,changed)
        codes=[]
        for source in (template,changed):
            validation=check(source,target='user',file='editor://htmlk-program.html')
            self.assertTrue(validation['ok'],validation)
            code=compile_html(source,target='user')
            self.assertEqual(validation['generated_c_sha256'],hashlib.sha256(code.encode()).hexdigest())
            codes.append(code)
        self.assertNotEqual(codes[0],codes[1])
        self.assertEqual(hashlib.sha256(codes[0].encode()).hexdigest(),
                         'c776330a638300731a1a23eeef9a1b68b6b511915d0db5e28e22ff8534c23bfc')
        self.assertEqual(hashlib.sha256(codes[1].encode()).hexdigest(),
                         '74f31f1b58eec45a9420534a255e286280fb8d5347d08fd2566aed1572750f9c')
        invalid=template.replace('<print value="value"/>','<prnit value="value"/>')
        result=check(invalid,target='user',file='editor://htmlk-program.html')
        self.assertFalse(result['ok'])
        self.assertIsNone(result['generated_c_sha256'])
        self.assertEqual(result['diagnostics'][0]['code'],'HK101_TAG')
        self.assertEqual(result['diagnostics'][0]['line'],5)
        self.assertEqual(result['diagnostics'][0]['column'],5)
        self.assertIn('Did you mean <print>?',result['diagnostics'][0]['hint'])


if __name__=='__main__':
    unittest.main()
