"""M2 if/else grammar, scoped codegen, resource and rejection contracts."""
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile

from compiler.htmlk import CompileError, compile_html


def wrap(boot, functions=""):
    return f'<kernel arch="x86_64">{functions}<onboot>{boot}</onboot></kernel>'


def func(body):
    return (f'<function name="choose" params="x:u64" returns="u64">'
            f'{body}</function>')


class ElseTests(unittest.TestCase):
    def reject(self, boot, reason, functions=""):
        with self.assertRaisesRegex(CompileError, reason):
            compile_html(wrap(boot, functions))

    def test_basic_else_codegen_on_both_targets(self):
        program = wrap(
            '<if test="2 &gt; 3"><print>bad</print>'
            '<else><print>correct</print></else></if><halt/>')
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                c = compile_html(program, target=target)
                self.assertIn('if ((UINT64_C(2) > UINT64_C(3))) {', c)
                self.assertIn('} else {', c)
                self.assertIn('0x63, 0x6f, 0x72, 0x72', c)

    def test_nested_conditionals_inside_else(self):
        c = compile_html(wrap(
            '<if test="1 == 2"><print>bad</print><else>'
            '<if test="2 == 2"><print>yes</print>'
            '<else><print>other</print></else></if>'
            '</else></if>'))
        self.assertGreaterEqual(c.count('} else {'), 2)

    def test_function_else_local_shadow_and_early_returns(self):
        functions = func(
            '<let name="sum" type="u64" value="x"/>'
            '<if test="x &gt; 10">'
            '<let name="z" type="u64" value="2"/>'
            '<return value="sum + z"/>'
            '<else>'
            '<let name="z" type="u64" value="5"/>'
            '<set name="sum" value="sum + z"/>'
            '<return value="sum"/>'
            '</else></if>'
            '<return value="0"/>')
        code = compile_html(wrap('<print value="choose(3)"/>', functions))
        self.assertIn('htmlk_local_choose_1', code)
        self.assertIn('htmlk_local_choose_2', code)
        self.assertIn('} else {', code)

    def test_false_branch_can_modify_outer_function_variable(self):
        code = compile_html(wrap(
            '<print value="choose(1)"/>',
            func('<let name="sum" type="u64" value="0"/>'
                 '<if test="x == 0">'
                 '<set name="sum" value="1"/>'
                 '<else><set name="sum" value="2"/></else></if>'
                 '<return value="sum"/>')))
        self.assertIn('htmlk_local_choose_0 = UINT64_C(2);', code)

    def test_orphan_else_rejected(self):
        self.reject('<else><print>oops</print></else>', 'not allowed')
        self.reject('<repeat times="1"><else><print>oops</print></else></repeat>',
                    'not allowed')
        self.reject('<if test="1 == 1"><else><print>ok</print>'
                    '</else></if><else><print>bad</print></else>', 'not allowed')

    def test_else_must_be_last_and_unique(self):
        self.reject('<if test="1 == 1"><else><print>a</print>'
                    '</else><print>b</print></if>', 'must be the final')
        self.reject('<if test="1 == 1"><else><print>a</print></else>'
                    '<else><print>b</print></else></if>', 'at most one')

    def test_else_attributes_and_text_rejected(self):
        self.reject('<if test="1 == 1"><else extra="1">'
                    '<print>ok</print></else></if>', 'invalid attributes')
        self.reject('<if test="1 == 1"><else>raw text</else></if>', 'text is only')
        self.reject('<if test="1 == 1"><else value="">'
                    '<print>ok</print></else></if>', 'invalid attributes')

    def test_else_branch_variable_leak_rejected(self):
        self.reject('<print value="choose(4)"/>', 'undefined variable',
                    func('<if test="x == 4"><return value="4"/>'
                         '<else><let name="local" type="u64" value="4"/>'
                         '</else></if><return value="local"/>'))
        self.reject('<print value="choose(4)"/>', 'undefined variable',
                    func('<if test="x == 4">'
                         '<let name="local" type="u64" value="4"/>'
                         '<else><return value="local"/></else></if>'
                         '<return value="x"/>'))
        self.reject('<if test="1 == 2"><print>ok</print><else>'
                    '<let name="no" type="u64" value="2"/>'
                    '</else></if><print value="no"/>', 'undefined variable')

    def test_unreachable_after_return_inside_else_rejected(self):
        self.reject('<print value="choose(4)"/>', 'unreachable',
                    func('<if test="x == 4"><return value="4"/>'
                         '<else><return value="2"/>'
                         '<set name="x" value="3"/></else></if>'
                         '<return value="0"/>'))

    def test_else_counts_toward_output_limit_even_if_branch_false(self):
        self.reject('<repeat times="64">'
                    '<if test="2 == 2"><print>ok</print>'
                    '<else><print>' + ("x" * 300) +
                    '</print></else></if></repeat>', 'estimated output exceeds')

    def test_else_counts_toward_function_work_budget(self):
        self.reject('<print value="choose(1)"/>', 'function statement work budget',
                    func('<repeat times="64">'
                         '<if test="x == 1"><set name="x" value="2"/>'
                         '<else><repeat times="64"><repeat times="64">'
                         '<set name="x" value="3"/>'
                         '</repeat></repeat></else></if></repeat>'
                         '<return value="x"/>'))

    def test_cli_errors_include_source_filename_and_position(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "typo.html"
            dest = Path(temp) / "bad.c"
            src.write_text(wrap(
                '<if test="1 == 1"><else></else>'
                '<print>should fail</print></if>'), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "compiler/htmlk.py", str(src),
                 "--target", "linux", "--out", str(dest)],
                capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(src), result.stderr)
            self.assertIn("line 1, column", result.stderr)
            self.assertIn("<else> must be the final child", result.stderr)
            self.assertFalse(dest.exists())

    def test_unescaped_less_than_in_attribute_not_silently_accepted(self):
        # HTML attributes tolerate literal < in some parsers. Our expressions
        # still typecheck, and supported syntax is deliberately documented.
        code = compile_html(wrap(
            '<if test="1 &lt; 2"><print>yes</print>'
            '<else><print>no</print></else></if>'))
        self.assertIn('UINT64_C(1) < UINT64_C(2)', code)


if __name__ == "__main__":
    unittest.main()
