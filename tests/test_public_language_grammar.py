"""Public grammar metadata must match the one actual compiler and parser."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compiler.diagnostics import describe
from compiler.htmlk import compile_html
from compiler.language import CHILDREN, ALLOWED, REQUIRED

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'scripts/build_public_language_grammar.py'


class PublicGrammarTests(unittest.TestCase):
    def test_generator_is_deterministic_and_exact_compiler_derived(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)/'language.json'
            for _ in range(2):
                result = subprocess.run([sys.executable,str(BUILD),'--out',str(source)],
                                        capture_output=True,timeout=6)
                self.assertEqual(result.returncode,0,result.stderr)
                metadata=json.loads(source.read_text())
                self.assertEqual(len(metadata['tags']),18)
                self.assertEqual({k:metadata[k] for k in describe()},describe())
                self.assertEqual(set(metadata['tags']),set(CHILDREN))
                for tag in CHILDREN:
                    self.assertEqual(set(metadata['tags'][tag]['attributes']),ALLOWED[tag])
                    self.assertEqual(set(metadata['tags'][tag]['required_attributes']),
                                     REQUIRED.get(tag,set()))
                self.assertLessEqual(source.stat().st_size,16384)
                self.assertEqual(metadata['compiler_source_sha256']['compiler/language.py'],
                                 hashlib.sha256((ROOT/'compiler/language.py').read_bytes()).hexdigest())
                before=source.read_bytes()
                self.assertEqual(subprocess.run([sys.executable,str(BUILD),
                                                  '--out',str(source)],capture_output=True).returncode,0)
                self.assertEqual(source.read_bytes(),before)

    def test_main_effective_parent_aliases_use_single_typed_codegen(self):
        grammar=describe()
        self.assertIn('main',grammar['tags']['print']['parents'])
        self.assertIn('main',grammar['tags']['halt']['parents'])
        self.assertIn('onboot',grammar['tags']['print']['parents'])
        self.assertEqual(grammar['tags']['main']['parents'],['program'])
        source='<program><main><print value="9"/><halt/></main></program>'
        traditional='<kernel><onboot><print value="9"/><halt/></onboot></kernel>'
        for target in ('linux','user'):
            self.assertEqual(compile_html(source,target=target),
                             compile_html(traditional,target=target))

    def test_generator_never_follows_symlink_or_creates_missing_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sensitive=root/'existing'
            sensitive.write_text('PRESERVE')
            link=root/'symlink.json'
            link.symlink_to(sensitive)
            for output in (link,root/'absent-dir'/'output.json'):
                done=subprocess.run([sys.executable,str(BUILD),'--out',str(output)],
                                    capture_output=True,timeout=6)
                self.assertNotEqual(done.returncode,0)
            self.assertEqual(sensitive.read_text(),'PRESERVE')


if __name__=='__main__':
    unittest.main()
