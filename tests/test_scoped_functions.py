"""M2 multi-statement u64 functions, lexical locals and return safety."""
import unittest

from compiler.htmlk import CompileError, compile_html


def source(body, params="n:u64", boot='<print value="f(4)"/>'):
    return (f'<kernel arch="x86_64"><function name="f" params="{params}" '
            f'returns="u64">{body}</function><onboot>{boot}</onboot></kernel>')


class ScopedFunctionTests(unittest.TestCase):
    def reject(self, body, reason, *, params="n:u64", boot='<print>ok</print>'):
        with self.assertRaisesRegex(CompileError, reason):
            compile_html(source(body, params=params, boot=boot))

    def test_multistatement_local_conditional_return_and_loop(self):
        code = compile_html(source(
            '<let name="sum" type="u64" value="0"/>'
            '<repeat times="3">'
            '<let name="piece" type="u64" value="n"/>'
            '<set name="sum" value="sum + piece"/>'
            '<set name="n" value="n + 1"/>'
            '</repeat>'
            '<if test="sum &gt; 10">'
            '<let name="sum" type="u64" value="sum + 5"/>'
            '<return value="sum"/>'
            '</if>'
            '<return value="sum"/>'
        ))
        self.assertIn('htmlk_local_f_0', code)
        self.assertIn('htmlk_local_f_1', code)
        self.assertIn('htmlk_local_f_2', code)
        self.assertIn('htmlk_repeat_f_0', code)
        self.assertIn('return htmlk_local_f_2;', code)
        self.assertIn('return htmlk_local_f_0;', code)

    def test_scope_shadowing_changes_only_inner_binding(self):
        code = compile_html(source(
            '<let name="n" type="u64" value="4"/>'
            '<if test="n == 4">'
            '<let name="n" type="u64" value="n + 3"/>'
            '<set name="n" value="n + 2"/>'
            '</if>'
            '<return value="n"/>',
            params="",
            boot='<print value="f()"/>'))
        self.assertIn('htmlk_local_f_0 =', code)
        self.assertIn('htmlk_local_f_1 =', code)
        self.assertIn('htmlk_local_f_1 = ((uint64_t)', code)
        self.assertIn('return htmlk_local_f_0;', code)

    def test_outer_variable_can_be_updated_inside_loop(self):
        code = compile_html(source(
            '<let name="counter" type="u64" value="0"/>'
            '<repeat times="3"><set name="counter" value="counter + 1"/></repeat>'
            '<return value="counter"/>'))
        self.assertIn('htmlk_local_f_0 = ((uint64_t)', code)

    def test_shadow_same_scope_rejected(self):
        self.reject('<let name="x" type="u64" value="1"/>'
                    '<let name="x" type="u64" value="2"/><return value="x"/>',
                    "already declared")
        self.reject('<let name="n" type="u64" value="2"/><return value="n"/>',
                    "already declared")

    def test_out_of_scope_reference_rejected(self):
        self.reject('<if test="n == 1"><let name="x" type="u64" value="2"/></if>'
                    '<return value="x"/>', "undefined variable")
        self.reject('<repeat times="2"><let name="x" type="u64" value="2"/>'
                    '</repeat><return value="x"/>', "undefined variable")
        self.reject('<if test="n == 1"><let name="x" type="u64" value="2"/></if>'
                    '<set name="x" value="4"/><return value="n"/>',
                    "undefined variable")

    def test_missing_fallback_return_rejected(self):
        self.reject('<let name="x" type="u64" value="1"/>', "must end with")
        self.reject('<if test="n == 1"><return value="1"/></if>',
                    "must end with")
        self.reject('<repeat times="0"><return value="1"/></repeat>',
                    "must end with")

    def test_unreachable_statements_after_return_rejected(self):
        self.reject('<return value="1"/><set name="n" value="2"/>',
                    "must end with|unreachable")
        self.reject('<if test="n == 1"><return value="1"/>'
                    '<set name="n" value="2"/></if><return value="n"/>',
                    "unreachable")

    def test_returns_must_be_numeric_and_locals_typechecked(self):
        self.reject('<return value="n == 4"/>', "expected number")
        self.reject('<let name="x" type="i32" value="2"/><return value="x"/>',
                    'only type="u64"')
        self.reject('<let name="x" type="u64" value="n == 2"/>'
                    '<return value="x"/>', "expected number")
        self.reject('<let name="x" type="u64" value="n"/>'
                    '<if test="x"><return value="x"/></if>'
                    '<return value="x"/>', "expected boolean")

    def test_illegal_return_and_print_in_wrong_context(self):
        self.reject('<print>illegal</print><return value="n"/>',
                    "not allowed")
        with self.assertRaisesRegex(CompileError, "not allowed"):
            compile_html('<kernel><onboot><print>ok</print>'
                         '<return value="2"/></onboot></kernel>')

    def test_calls_are_checked_inside_branches(self):
        func = '<function name="f" params="" returns="u64">'
        func += '<if test="2 == 2"><return value="missing(2)"/></if>'
        func += '<return value="0"/></function>'
        with self.assertRaisesRegex(CompileError, "undefined function"):
            compile_html('<kernel>' + func +
                         '<onboot><print value="f()"/></onboot></kernel>')

    def test_nested_recursion_rejected_even_when_branch_not_taken(self):
        self.reject('<repeat times="0"><return value="f(n)"/></repeat>'
                    '<return value="n"/>', "recursive function")

    def test_unused_parameter_and_local_compile_with_werror(self):
        generated = compile_html(source(
            '<let name="not_used" type="u64" value="5"/>'
            '<return value="7"/>'))
        self.assertIn('(void)htmlk_n;', generated)
        self.assertIn('(void)htmlk_local_f_0;', generated)

    def test_function_body_budget_includes_loop_statements(self):
        # Nested loops of 64x64x64 exceed 20,000 source steps.
        self.reject('<repeat times="64">' * 3 + '<set name="n" value="n + 1"/>'
                    + '</repeat>' * 3 + '<return value="n"/>',
                    "function statement work budget exceeded")


if __name__ == "__main__":
    unittest.main()
