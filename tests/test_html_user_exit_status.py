"""M5-F4: strict HTML user exit code, kernel/Linux targets unchanged."""
from pathlib import Path
import unittest
from compiler.htmlk import compile_html
from compiler.language import CompileError, parse

ROOT=Path(__file__).resolve().parents[1]
BASE=(ROOT/'examples/user-programs/html-message.html').read_text()
assert BASE.count('<halt/>')==1

class HtmlUserExitStatusTests(unittest.TestCase):
    def test_native_user_exit_code_0_7_255(self):
        for code in ('0','7','255','007'):
            with self.subTest(code=code):
                src=BASE.replace('<halt/>',f'<halt code="{code}"/>')
                output=compile_html(src,target='user')
                self.assertIn(f'htmlk_user_call(UINT64_C(1), UINT64_C({int(code)}))',output)
                self.assertNotIn('io_outb(',output)
                self.assertEqual(output,compile_html(src,target='user'))
        self.assertIn('htmlk_user_call(UINT64_C(1), UINT64_C(0))',
                      compile_html(BASE,target='user'))

    def test_kernel_and_linux_reject_exit_code_attribute(self):
        for target in ('kernel','linux'):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError,'only valid for native Ring3'):
                    compile_html(BASE.replace('<halt/>','<halt code="7"/>'),target=target)
                # Existing ordinary halt remains legal on both targets.
                compile_html(BASE,target=target)

    def test_out_of_range_or_noncanonical_numeric_attributes_rejected(self):
        for value in ('-1','256','999','1000','0x10','1+1','1.0',
                      '+1',' 7','7 ','', '７','1e0'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CompileError,'halt code'):
                    compile_html(BASE.replace('<halt/>',f'<halt code="{value}"/>'),
                                 target='user')
        with self.assertRaises(CompileError):
            parse(BASE.replace('<halt/>','<halt code="1" code="2"/>'))
        with self.assertRaises(CompileError):
            parse(BASE.replace('<halt/>','<halt exit="7"/>'))

    def test_only_final_unconditional_halt_accepts_status(self):
        src=BASE.replace('<halt/>','<halt code="7"/><print>late</print>')
        with self.assertRaises(CompileError):compile_html(src,target='user')

if __name__=='__main__':unittest.main()
