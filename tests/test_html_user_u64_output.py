"""M5-F5 host source checks for the complete unsigned 64-bit user report ABI."""
from pathlib import Path
import unittest
from compiler.htmlk import compile_html
from compiler.language import CompileError

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'examples/user-programs/html-u64-report.html').read_text()

class HtmlUserU64OutputTests(unittest.TestCase):
    def test_emits_true_unsigned_64_bit_literals_and_exit_code(self):
        generated=compile_html(SOURCE,target='user')
        self.assertIn('UINT64_C(4294967296)',generated)
        self.assertIn('UINT64_C(18446744073709551615)',generated)
        self.assertIn('htmlk_user_call(UINT64_C(2)',generated)
        self.assertIn('htmlk_user_call(UINT64_C(1), UINT64_C(7))',generated)
        self.assertNotIn('io_outb(',generated)
        self.assertEqual(generated,compile_html(SOURCE,target='user'))

    def test_output_zero_9999_10000_u32_overflow_and_u64_max(self):
        for value in ('0','9999','10000','4294967295',
                      '4294967296','18446744073709551615'):
            with self.subTest(value=value):
                changed=SOURCE.replace('18446744073709551615',value)
                self.assertIn(f'UINT64_C({value})',compile_html(changed,target='user'))

    def test_source_denies_above_u64_and_signed_reports(self):
        for bad in ('18446744073709551616','340282366920938463463374607431768211455'):
            with self.subTest(bad=bad):
                with self.assertRaises(CompileError):
                    compile_html(SOURCE.replace('18446744073709551615',bad),target='user')
        signed=SOURCE.replace('<print value="18446744073709551615"/>',
                              '<let name="negative" type="i64" value="-1"/>'
                              '<print value="negative"/>')
        with self.assertRaisesRegex(CompileError,'unsigned'):
            compile_html(signed,target='user')

    def test_kernel_and_linux_targets_keep_existing_numeric_compilation(self):
        for target in ('kernel','linux'):
            with self.subTest(target=target):
                source=SOURCE.replace('<halt code="7"/>','<halt/>')
                generated=compile_html(source,target=target)
                self.assertIn('htmlk_print_u64(',generated)
                self.assertNotIn('htmlk_user_call',generated)

    def test_report_budget_remains_eight_in_user_target(self):
        source=SOURCE.replace('times="2"','times="7"')
        self.assertIn('htmlk_user_call',compile_html(source,target='user'))
        with self.assertRaisesRegex(CompileError,'budget exceeds 8'):
            compile_html(source.replace('times="7"','times="8"'),target='user')

if __name__=='__main__':unittest.main()
