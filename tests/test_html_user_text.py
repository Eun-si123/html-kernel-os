"""User text compiler shares M2 grammar; kernel copyin remains bounded."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from compiler.htmlk import compile_html
from compiler.language import CompileError
from scripts.build_html_user_image import assert_safe_relocations
from scripts.build_user_image import fnv1a

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'examples/user-programs/html-message.html'

class HtmlUserTextTests(unittest.TestCase):
    def test_c_backend_text_is_readonly_and_no_raw_port_access(self):
        generated=compile_html(APP.read_text(),target='user')
        self.assertIn('static const unsigned char message[]',generated)
        self.assertIn('htmlk_user_call_text(message, sizeof(message))',generated)
        self.assertIn('"int $0x80"',generated)
        self.assertNotIn('outb',generated)
        self.assertIn('0x48, 0x65, 0x6c, 0x6c, 0x6f',generated)

    def test_ascii_bounds_and_no_terminal_control_in_user_source(self):
        source=APP.read_text()
        for bad in ('한글','bad\tescape','X'*96,'x\x1b[31m','one\rline'):
            with self.subTest(value=bad[:15]):
                with self.assertRaises(CompileError):
                    compile_html(source.replace('Hello from HTML user mode!',bad),
                                 target='user')
        self.assertIn('user_call_text',compile_html(
            source.replace('Hello from HTML user mode!','A'*95),target='user'))

    def test_forbid_absolute_relocations_resolved_by_final_link(self):
        assert_safe_relocations('There are no relocations in this file.')
        assert_safe_relocations('000000000036  000300000002 R_X86_64_PC32 X + 0')
        assert_safe_relocations('000000000036  000300000004 R_X86_64_PLT32 Y - 4')
        for kind in ('R_X86_64_32','R_X86_64_64','R_X86_64_GOTPCREL'):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError,'unsupported relocation'):
                    assert_safe_relocations('000000000036  00030000000a '+kind+' .rodata + 0')

    def test_native_hkex_keeps_literal_inside_one_code_page(self):
        from scripts.build_html_user_image import build
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'app.hke';image=build(APP,out)
            self.assertEqual(image,out.read_bytes())
            self.assertIn(b'Hello from HTML user mode!\n',image[32:])
            self.assertEqual(int.from_bytes(image[16:20],'little'),fnv1a(image[32:]))
            self.assertLessEqual(len(image),4096)

if __name__=='__main__':unittest.main()
