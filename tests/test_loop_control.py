"""Break/continue only inside bounded repeats, both backends, strict control flow."""
import unittest

from compiler.htmlk import compile_html, CompileError


def program(body: str, f: str = "") -> str:
    return f'<kernel arch="x86_64">{f}<onboot><print>loops</print>{body}</onboot></kernel>'


def function(body: str) -> str:
    return f'<function name="f" params="x:i32" returns="i32">{body}</function>'


class LoopControlTests(unittest.TestCase):
    def reject(self, body: str, reason: str, funcs: str = ""):
        for target in ("linux", "kernel"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, reason):
                    compile_html(program(body, funcs), target=target)

    def test_direct_break_in_repeat(self):
        c = compile_html(program(
            '<repeat times="3"><if test="1 == 1"><break/></if></repeat>'))
        self.assertIn('break;', c)
        self.assertIn('for (uint64_t htmlk_loop_0', c)

    def test_direct_continue_in_repeat(self):
        c = compile_html(program(
            '<repeat times="3"><continue/></repeat>'))
        self.assertIn('continue;', c)

    def test_nested_if_else_and_repeats_target_nearest_loop(self):
        code = compile_html(program(
            '<repeat times="4">'
            '<repeat times="3">'
            '<if test="1 == 2"><break/><else><continue/></else></if>'
            '</repeat></repeat>'))
        self.assertIn('htmlk_loop_1', code)
        self.assertIn('break;', code)
        self.assertIn('continue;', code)

    def test_function_break_continue_inside_bounded_loop(self):
        functions = function(
            '<let name="n" type="i32" value="x"/>'
            '<repeat times="5">'
            '<set name="n" value="n + 1"/>'
            '<if test="n == 0"><continue/></if>'
            '<if test="n == 3"><break/></if>'
            '</repeat><return value="n"/>')
        code = compile_html(program('<print value="f(-2)"/>', functions))
        self.assertIn('break;', code)
        self.assertIn('continue;', code)
        self.assertIn('int32_t htmlk_fn_f(int32_t htmlk_v_x)', code)

    def test_reject_break_outside_repeat(self):
        self.reject('<break/>', "not allowed|requires")
        self.reject('<if test="1 == 1"><break/></if>', "requires")
        self.reject('<if test="1 == 1"><else><break/></else></if>', "requires")
        self.reject('<print value="f(1)"/>', "requires",
                    function('<if test="x == 1"><break/></if><return value="x"/>'))

    def test_reject_continue_outside_repeat(self):
        self.reject('<continue/>', "not allowed|requires")
        self.reject('<if test="1 == 1"><continue/></if>', "requires")
        self.reject('<print value="f(1)"/>', "requires",
                    function('<if test="x == 1"><continue/></if><return value="x"/>'))

    def test_reject_attributes_and_content(self):
        self.reject('<repeat times="1"><break why="not-supported"/></repeat>',
                    "invalid attributes")
        self.reject('<repeat times="1"><continue count="2"/></repeat>',
                    "invalid attributes")
        self.reject('<repeat times="1"><break>text</break></repeat>',
                    "text is only")
        self.reject('<repeat times="1"><break><print>bad</print></break></repeat>',
                    "not allowed")

    def test_reject_unreachable_after_break_in_same_function_block(self):
        funcs = function(
            '<repeat times="2">'
            '<break/><set name="x" value="x + 1"/>'
            '</repeat><return value="x"/>')
        self.reject('<print value="f(1)"/>', "unreachable", funcs)

    def test_reject_unreachable_after_continue_in_same_function_block(self):
        funcs = function(
            '<repeat times="2">'
            '<if test="x == 1">'
            '<continue/><set name="x" value="2"/>'
            '</if>'
            '</repeat><return value="x"/>')
        self.reject('<print value="f(1)"/>', "unreachable", funcs)

    def test_no_fallthrough_when_continue_is_last_in_if_branch(self):
        funcs = function(
            '<repeat times="2">'
            '<if test="x == 1"><continue/>'
            '<else><break/></else></if>'
            '</repeat><return value="x"/>')
        code = compile_html(program('<print value="f(1)"/>', funcs))
        self.assertIn('} else {', code)
        self.assertIn('continue;', code)
        self.assertIn('break;', code)

    def test_lexical_variables_still_do_not_escape_loop(self):
        self.reject('<print value="f(1)"/>', "undefined variable",
                    function('<repeat times="2">'
                             '<let name="inner" type="i32" value="x"/>'
                             '<break/></repeat>'
                             '<return value="inner"/>'))

    def test_source_statement_work_limits_remain_conservative(self):
        big = '<repeat times="64">' * 3 + '<continue/>' + '</repeat>' * 3
        self.reject(big, "estimated work exceeds")
        bigfunc = '<repeat times="64">' * 3 + '<continue/>' + '</repeat>' * 3
        self.reject('<print value="f(1)"/>',
                    "function statement work budget exceeded",
                    function(bigfunc + '<return value="x"/>'))

    def test_an_empty_bounded_loop_compiles(self):
        code = compile_html(program(
            '<repeat times="0"><break/></repeat>'
            '<repeat times="0"><continue/></repeat>'))
        self.assertIn('< UINT64_C(0)', code)


if __name__ == "__main__":
    unittest.main()
