"""TinyCC adapter refuses unsupported ELF layouts and never relaxes GCC proof."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from compiler.htmlk import compile_html
from scripts.build_tcc_html_user_image import (
    adapt_generated_c, allocated_sections, require_tcc_sections, undefined_symbols, build,
)
from scripts.build_html_user_image import assert_safe_relocations

ROOT=Path(__file__).resolve().parents[1]


class TinyCCNativeContractTests(unittest.TestCase):
    def test_literal_is_explicit_rodata_and_unknown_user_c_is_rejected(self):
        original=compile_html((ROOT/'examples/user-programs/html-message.html').read_text(),target='user')
        adapted=adapt_generated_c(original)
        self.assertIn('message[] __attribute__((section(".rodata")))',adapted)
        self.assertIn('__asm__ volatile ("ud2");',adapted)
        self.assertNotIn('__builtin_unreachable();',adapted)
        self.assertEqual(adapt_generated_c(original),adapted)
        self.assertEqual(original,compile_html((ROOT/'examples/user-programs/html-message.html').read_text(),target='user'))
        for modified in ('int main() {}',original.replace('"int $0x80"','"nop"'),original.replace('#include <stdint.h>','')):
            with self.subTest(modified=modified[:30]),self.assertRaises(ValueError):
                adapt_generated_c(modified)

    def test_relocation_policy_remains_only_pc_relative(self):
        for kind in ('R_X86_64_32','R_X86_64_64','R_X86_64_GOTPCREL','R_X86_64_32S'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                assert_safe_relocations('00000000  00000100 '+kind+' .data + 0')
        for kind in ('R_X86_64_PC32','R_X86_64_PLT32'):
            assert_safe_relocations('00000000  00000100 '+kind+' .rodata - 4')

    def test_allocated_object_sections_are_strictly_readonly(self):
        example='''There are 8 section headers, starting at offset 0x0:
  [Nr] Name              Type Address Off Size ES Flg Lk Inf Al
  [ 1] .text             PROGBITS        0000000000000000 000040 000100 00  AX  0   0  8
  [ 2] .rodata           PROGBITS        0000000000000000 000140 00001b 00   A  0   0  8
  [ 3] .data             PROGBITS        0000000000000000 000160 000000 00  WA  0   0  8
  [ 4] .bss              NOBITS          0000000000000000 000160 000000 00  WA  0   0  8
'''
        self.assertEqual(allocated_sections(example)[0],('.text',256,'AX'))
        self.assertEqual(allocated_sections(example)[1],('.rodata',27,'A'))
        final='''  [ 1] .text             PROGBITS        0000000000000000 001000 000120 00  AX  0   0  8'''
        require_tcc_sections(example,final)
        data=example.replace('000000 00  WA','000001 00  WA')
        with self.assertRaisesRegex(ValueError,'unsupported allocated TinyCC section'):
            require_tcc_sections(data,final)
        with self.assertRaisesRegex(ValueError,'writable sections'):
            require_tcc_sections(example,example.replace('000000 00  WA','00001b 00  WA'))
        with self.assertRaisesRegex(ValueError,'unsupported allocated TinyCC section'):
            require_tcc_sections(example.replace('.rodata','.tls'),final)
        with self.assertRaisesRegex(ValueError,'unsupported allocated ELF section type'):
            require_tcc_sections(example.replace('PROGBITS        0000000000000000 000140',
                                                 'INIT_ARRAY      0000000000000000 000140'),final)

    def test_only_tcc_memset_undefined_symbol_is_allowed(self):
        table='''Symbol table '.symtab' contains 3 entries:
     0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND
     1: 0000000000000000 0 FUNC GLOBAL DEFAULT UND memset
     2: 0000000000000000 0 FUNC GLOBAL DEFAULT UND memcpy
'''
        self.assertEqual(undefined_symbols(table),{'memset','memcpy'})
        self.assertEqual(undefined_symbols(table.replace('memcpy','')),{'memset'})
        self.assertEqual(undefined_symbols('     0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND\n'),set())

    def test_source_and_output_bounds_and_symlink_denial_before_compiler(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            good=directory/'good.html'
            good.write_bytes((ROOT/'examples/user-programs/html-message.html').read_bytes())
            victim=directory/'keep.txt';victim.write_text('KEEP')
            link=directory/'link.html';link.symlink_to(good)
            outlink=directory/'out.hke';outlink.symlink_to(victim)
            for source,out in ((link,directory/'unused.hke'),(good,outlink)):
                with self.subTest(source=source,out=out),self.assertRaises(ValueError):
                    build(source,out,tcc='/bin/false')
            self.assertEqual(victim.read_text(),'KEEP')
            too_large=directory/'too-large.html'
            too_large.write_bytes(b'A'*4097)
            with self.assertRaisesRegex(ValueError,'4096'):
                build(too_large,directory/'bad.hke',tcc='/bin/false')
            missing=directory/'missing.html'
            with self.assertRaises(ValueError):
                build(missing,directory/'bad.hke',tcc='/bin/false')

if __name__=='__main__':unittest.main()
