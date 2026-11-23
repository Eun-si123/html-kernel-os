"""M5-F3: shared HTML grammar, bounded report count and loop expansion."""
from __future__ import annotations
from pathlib import Path
import unittest

from compiler.htmlk import compile_html
from compiler.language import CompileError

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'examples/user-programs/html-multireport.html').read_text()


class HtmlUserMultiReportTests(unittest.TestCase):
    def test_repeated_text_and_numeric_final_report_compile(self):
        generated=compile_html(SOURCE,target='user')
        self.assertIn('htmlk_loop_0',generated)
        self.assertIn('htmlk_user_call_text',generated)
        self.assertIn('UINT64_C(2026)',generated)
        self.assertIn('htmlk_user_call(UINT64_C(1), UINT64_C(0))',generated)
        self.assertNotIn('outb',generated)
        self.assertEqual(generated,compile_html(SOURCE,target='user'))

    def test_bounded_if_else_and_while_reports(self):
        original=SOURCE.replace('<repeat times="2"><print>tick</print></repeat>',
            '<if test="1 == 1"><print>yes</print><else><print>no</print></else></if>'
            '<while test="1 == 1" max="3"><print>go</print><break/></while>')
        output=compile_html(original,target='user')
        self.assertIn('htmlk_user_call_text',output)
        self.assertIn('if (',output)
        self.assertIn('for (',output)

    def test_static_estimate_denies_nine_reports_and_no_mandatory_final(self):
        samples=[
          SOURCE.replace('times="2"','times="8"'),
          SOURCE.replace('<print value="2026"/>',
                         '<repeat times="2"><print value="2026"/></repeat>'),
          SOURCE.replace('times="2"','times="64"'),
          SOURCE.replace('<print value="2026"/>',
                         '<if test="1 == 1"><print value="2026"/></if>'),
          SOURCE.replace('<print value="2026"/>',''),
        ]
        for sample in samples:
            with self.subTest(sample=sample[-130:]):
                with self.assertRaises(CompileError):compile_html(sample,target='user')

    def test_eight_total_reports_are_allowed_but_no_more(self):
        content=SOURCE.replace('times="2"','times="7"')
        self.assertIn('htmlk_user_call_text',compile_html(content,target='user'))
        with self.assertRaisesRegex(CompileError,'budget'):
            compile_html(content.replace('times="7"','times="8"'),target='user')


if __name__=='__main__':unittest.main()
