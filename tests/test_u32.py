"""Strict u32/u64 semantics, explicit casts, type-safe function calls."""
from __future__ import annotations

import unittest
from compiler.htmlk import compile_html, CompileError


def program(body: str, funcs: str = "") -> str:
    return (f'<kernel arch="x86_64">{funcs}<onboot>'
            f'<print>type test</print>{body}<halt/></onboot></kernel>')


def fun(name: str, params: str, returns: str, body: str) -> str:
    return f'<function name="{name}" params="{params}" returns="{returns}">{body}</function>'


class U32Tests(unittest.TestCase):
    def rejected(self, body: str, reason: str, funcs: str = "") -> None:
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, reason):
                    compile_html(program(body, funcs), target=target)

    def test_u32_native_type_emitted_on_both_targets(self):
        html = program('<let name="x" type="u32" value="5"/>'
                       '<set name="x" value="x + 3"/>'
                       '<print value="x"/>')
        for target in ("kernel", "linux"):
            code = compile_html(html, target=target)
            self.assertIn('uint32_t htmlk_x = UINT32_C(5);', code)
            self.assertIn('htmlk_x = ((uint32_t)(htmlk_x + UINT32_C(3)));', code)
            self.assertIn('htmlk_print_u64(htmlk_x);', code)

    def test_u32_max_and_modulo_wrap(self):
        code = compile_html(program(
            '<let name="max" type="u32" value="4294967295"/>'
            '<set name="max" value="max + 1"/>'
            '<print value="max"/>'))
        self.assertIn('uint32_t htmlk_max = UINT32_C(4294967295);', code)
        self.assertIn('((uint32_t)(htmlk_max + UINT32_C(1)))', code)

    def test_u32_subtract_and_multiply_wrap(self):
        code = compile_html(program(
            '<let name="x" type="u32" value="0"/>'
            '<set name="x" value="x - 1"/>'
            '<set name="x" value="x * 2"/>'
            '<print value="x"/>'))
        self.assertIn('((uint32_t)(htmlk_x - UINT32_C(1)))', code)
        self.assertIn('((uint32_t)(htmlk_x * UINT32_C(2)))', code)

    def test_u32_literal_expression_uses_expected_type(self):
        code = compile_html(program(
            '<let name="a" type="u32" value="1 + 2 * 3"/>'
            '<print value="a"/>'))
        self.assertIn('uint32_t htmlk_a = ((uint32_t)(', code)
        self.assertIn('UINT32_C(1)', code)
        self.assertIn('UINT32_C(2)', code)
        self.assertIn('UINT32_C(3)', code)

    def test_u32_literal_out_of_range_rejected(self):
        self.rejected('<let name="x" type="u32" value="4294967296"/>',
                      'outside u32 range')
        self.rejected('<let name="x" type="u32" value="4294967295 + 4294967296"/>',
                      'outside u32 range')

    def test_explicit_narrow_and_widen_casts(self):
        code = compile_html(program(
            '<let name="wide" type="u64" value="4294967296"/>'
            '<let name="low" type="u32" value="u32(wide)"/>'
            '<let name="restore" type="u64" value="u64(low)"/>'
            '<print value="restore"/>'))
        self.assertIn('((uint32_t)(htmlk_wide))', code)
        self.assertIn('((uint64_t)(htmlk_low))', code)

    def test_casting_large_literal_to_u32_is_explicitly_allowed(self):
        code = compile_html(program(
            '<let name="x" type="u32" value="u32(4294967296)"/>'
            '<print value="x"/>'))
        self.assertIn('((uint32_t)(UINT64_C(4294967296)))', code)

    def test_no_implicit_narrowing_or_widening(self):
        self.rejected(
            '<let name="wide" type="u64" value="5"/>'
            '<let name="small" type="u32" value="wide"/>',
            'expected u32 expression but got u64')
        self.rejected(
            '<let name="small" type="u32" value="5"/>'
            '<let name="wide" type="u64" value="small"/>',
            'expected u64 expression but got u32')
        self.rejected(
            '<let name="wide" type="u64" value="5"/>'
            '<let name="small" type="u32" value="wide + 1"/>',
            'expected u32 expression but got u64')
        self.rejected(
            '<let name="wide" type="u64" value="5"/>'
            '<let name="small" type="u32" value="5"/>'
            '<set name="small" value="wide"/>',
            'expected u32 expression but got u64')

    def test_mixed_width_arithmetic_and_comparison_rejected(self):
        body = ('<let name="small" type="u32" value="1"/>'
                '<let name="wide" type="u64" value="1"/>')
        self.rejected(body + '<print value="small + wide"/>',
                      'cannot mix u32 and u64')
        self.rejected(body + '<if test="small == wide">'
                      '<print>bad</print></if>',
                      'cannot mix u32 and u64')

    def test_u32_comparison_literal_boundary(self):
        code = compile_html(program(
            '<let name="x" type="u32" value="2"/>'
            '<if test="x &lt; 3"><print>yes</print></if>'))
        self.assertIn('htmlk_x < UINT32_C(3)', code)
        self.rejected('<let name="x" type="u32" value="1"/>'
                      '<if test="x &lt; 4294967296"><print>bad</print></if>',
                      'outside u32 range')

    def test_u32_function_parameters_and_return_codegen(self):
        functions = fun("inc", "x:u32", "u32", '<return value="x + 1"/>')
        code = compile_html(program('<print value="inc(4)"/>', functions))
        self.assertIn('uint32_t htmlk_fn_inc(uint32_t htmlk_x);', code)
        self.assertIn('uint32_t htmlk_fn_inc(uint32_t htmlk_x) {', code)
        self.assertIn('htmlk_print_u64(htmlk_fn_inc(UINT32_C(4)));', code)
        self.assertIn('return ((uint32_t)(htmlk_x + UINT32_C(1)));', code)

    def test_u32_function_parameter_mismatch(self):
        functions = fun("inc", "x:u32", "u32", '<return value="x + 1"/>')
        self.rejected(
            '<let name="wide" type="u64" value="2"/>'
            '<print value="inc(wide)"/>',
            'parameter.*requires u32', functions)
        self.rejected('<print value="inc(4294967296)"/>',
                      'outside u32 range', functions)
        self.rejected('<print value="inc(1 == 1)"/>',
                      'function arguments must be u32', functions)

    def test_u32_function_return_mismatch(self):
        funcs = fun("bad", "x:u64", "u32", '<return value="x"/>')
        self.rejected('<print value="bad(2)"/>',
                      'expected u32 expression but got u64', funcs)
        funcs = fun("bad", "x:u32", "u64", '<return value="x"/>')
        self.rejected('<print value="bad(2)"/>',
                      'expected u64 expression but got u32', funcs)

    def test_explicit_casts_in_functions_allow_cross_width(self):
        funcs = (
            fun("narrow", "x:u64", "u32", '<return value="u32(x)"/>') +
            fun("widen", "x:u32", "u64", '<return value="u64(x)"/>')
        )
        html = program(
            '<let name="wide" type="u64" value="4294967296"/>'
            '<print value="narrow(wide)"/>'
            '<print value="widen(narrow(wide))"/>', funcs)
        code = compile_html(html)
        self.assertIn('uint32_t htmlk_fn_narrow(uint64_t htmlk_x)', code)
        self.assertIn('uint64_t htmlk_fn_widen(uint32_t htmlk_x)', code)

    def test_scoped_shadowing_keeps_type_of_each_binding(self):
        functions = fun("shadow", "x:u32", "u32",
            '<let name="v" type="u32" value="x"/>'
            '<if test="v == 1">'
            '<let name="v" type="u64" value="4294967296"/>'
            '<set name="v" value="v + 1"/>'
            '</if>'
            '<return value="v"/>')
        code = compile_html(program('<print value="shadow(1)"/>', functions))
        self.assertIn('uint32_t htmlk_local_shadow_0', code)
        self.assertIn('uint64_t htmlk_local_shadow_1', code)
        self.assertIn('return htmlk_local_shadow_0;', code)

    def test_unsupported_types_and_cast_arguments_rejected(self):
        self.rejected('<let name="x" type="i16" value="1"/>',
                      'only type=')
        self.rejected('<print value="u32(1,2)"/>',
                      'conversion expects exactly 1 argument')
        self.rejected('<print value="u64(1 == 1)"/>',
                      'conversion requires an integer')
        self.rejected('<print value="u32(1).real"/>',
                      'unsupported expression syntax')
        functions = fun("u32", "x:u32", "u32", '<return value="x"/>')
        self.rejected('<print>ok</print>',
                      'reserved numeric conversion functions', functions)

    def test_old_u64_codegen_spelling_and_function_remains_compatible(self):
        original = program(
            '<let name="score" type="u64" value="2"/>'
            '<print value="score + 3"/>',
            fun("double", "v:u64", "u64", '<return value="v * 2"/>'))
        code = compile_html(original)
        self.assertIn('uint64_t htmlk_score = UINT64_C(2);', code)
        self.assertIn('htmlk_print_u64(((uint64_t)(htmlk_score + UINT64_C(3))));', code)
        self.assertIn('uint64_t htmlk_fn_double(uint64_t htmlk_v);', code)


if __name__ == "__main__":
    unittest.main()
