"""Signed i32/i64 range safety and typed native operations (M2)."""
import unittest

from compiler.htmlk import compile_html, CompileError


def program(body, functions=""):
    return f'<kernel arch="x86_64">{functions}<onboot><print>signed</print>{body}</onboot></kernel>'


def function(name, params, returns, body):
    return (f'<function name="{name}" params="{params}" returns="{returns}">'
            f'{body}</function>')


class SignedTests(unittest.TestCase):
    def reject(self, body, message, functions=""):
        for target in ("linux", "kernel"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, message):
                    compile_html(program(body, functions), target=target)

    def test_i32_boundaries(self):
        c = compile_html(program(
            '<let name="minimum" type="i32" value="-2147483648"/>'
            '<let name="maximum" type="i32" value="2147483647"/>'
            '<print value="minimum"/><print value="maximum"/>'))
        self.assertIn('int32_t htmlk_v_minimum = (-INT32_C(2147483647) - INT32_C(1));', c)
        self.assertIn('int32_t htmlk_v_maximum = INT32_C(2147483647);', c)
        self.assertIn('htmlk_print_i64((int64_t)(htmlk_v_minimum));', c)

    def test_i64_boundaries(self):
        c = compile_html(program(
            '<let name="minimum" type="i64" value="-9223372036854775808"/>'
            '<let name="maximum" type="i64" value="9223372036854775807"/>'
            '<print value="minimum"/><print value="maximum"/>'))
        self.assertIn('(-INT64_C(9223372036854775807) - INT64_C(1))', c)
        self.assertIn('INT64_C(9223372036854775807)', c)
        self.assertIn('htmlk_from_bits_i64', c)

    def test_wrap_helpers_use_unsigned_arithmetic_to_avoid_signed_ub(self):
        c = compile_html(program(
            '<let name="x" type="i32" value="-2"/>'
            '<set name="x" value="x * 2147483647"/>'
            '<print value="x + 3"/><print value="x - 1"/>'))
        self.assertIn('htmlk_mul_i32(htmlk_v_x, INT32_C(2147483647))', c)
        self.assertIn('htmlk_add_i32(htmlk_v_x, INT32_C(3))', c)
        self.assertIn('htmlk_sub_i32(htmlk_v_x, INT32_C(1))', c)
        self.assertIn('htmlk_from_bits_i32((uint32_t)a * (uint32_t)b)', c)
        self.assertNotIn('((int32_t)(htmlk_v_x *', c)

    def test_sign_change_and_unary_plus(self):
        c = compile_html(program(
            '<let name="x" type="i64" value="-1"/>'
            '<print value="-x"/><print value="+x"/>'))
        self.assertIn('htmlk_neg_i64(htmlk_v_x)', c)
        self.assertIn('htmlk_print_i64((int64_t)(htmlk_v_x))', c)

    def test_signed_comparison_and_boolean_branch(self):
        c = compile_html(program(
            '<let name="x" type="i32" value="-10"/>'
            '<if test="x &lt; 0 and x != 1"><print>yes</print></if>'))
        self.assertIn('htmlk_v_x < INT32_C(0)', c)
        self.assertIn('htmlk_v_x != INT32_C(1)', c)

    def test_nonimplicit_mixing_four_types(self):
        cases = [
            ('<let name="x" type="i32" value="4"/>'
             '<let name="y" type="u32" value="4"/><print value="x + y"/>'),
            ('<let name="x" type="i32" value="4"/>'
             '<let name="y" type="i64" value="4"/><print value="x + y"/>'),
            ('<let name="x" type="i64" value="4"/>'
             '<let name="y" type="u64" value="4"/><if test="x == y"><print>x</print></if>'),
            ('<let name="x" type="u32" value="4"/>'
             '<let name="y" type="u64" value="4"/><print value="x * y"/>'),
        ]
        for case in cases:
            self.reject(case, "cannot mix")

    def test_implicit_assignments_and_signed_functions_fail(self):
        fn = function("narrow", "x:i32", "i32", '<return value="x + 1"/>')
        self.reject('<let name="x" type="u32" value="1"/>'
                    '<print value="narrow(x)"/>',
                    "requires i32", fn)
        self.reject('<let name="x" type="i32" value="1"/>'
                    '<let name="y" type="u32" value="x"/>',
                    "expected u32 expression but got i32")
        self.reject('<let name="x" type="u32" value="1"/>'
                    '<set name="x" value="i32(1)"/>',
                    "expected u32 expression but got i32")

    def test_signed_function_param_return_codegen(self):
        f = (function("negate", "n:i64", "i64", '<return value="-n"/>') +
             function("min32", "", "i32", '<return value="-2147483648"/>'))
        code = compile_html(program(
            '<print value="negate(-1)"/>'
            '<print value="min32()"/>', f))
        self.assertIn('int64_t htmlk_fn_negate(int64_t htmlk_v_n);', code)
        self.assertIn('int32_t htmlk_fn_min32(void);', code)
        self.assertIn('return htmlk_neg_i64(htmlk_v_n);', code)
        self.assertIn('htmlk_print_i64((int64_t)(htmlk_fn_min32()))', code)

    def test_all_four_conversion_functions(self):
        c = compile_html(program(
            '<let name="x" type="u64" value="4294967295"/>'
            '<print value="i32(x)"/>'
            '<print value="i64(x)"/>'
            '<print value="u32(i64(-1))"/>'
            '<print value="u64(i32(-1))"/>'))
        self.assertIn('htmlk_from_bits_i32((uint32_t)(htmlk_v_x))', c)
        self.assertIn('htmlk_from_bits_i64((uint64_t)(htmlk_v_x))', c)
        self.assertIn('((uint32_t)(', c)
        self.assertIn('((uint64_t)(', c)

    def test_conversion_uses_wrap_and_does_not_depend_on_implementation_defined_c_cast(self):
        c = compile_html(program(
            '<print value="i64(u64(18446744073709551615))"/>'
            '<print value="i32(u32(4294967295))"/>'))
        self.assertIn('htmlk_from_bits_i64((uint64_t)(', c)
        self.assertIn('htmlk_from_bits_i32((uint32_t)(', c)
        self.assertIn('UINT64_C(18446744073709551615)', c)

    def test_positive_literal_range_enforced_for_signed_type(self):
        self.reject('<let name="x" type="i32" value="2147483648"/>', "outside i32 range")
        self.reject('<let name="x" type="i64" value="9223372036854775808"/>',
                    "outside i64 range")
        self.reject('<print value="i32(1 + 2 == 3)"/>', "requires an integer")

    def test_negative_literal_range_enforced(self):
        self.reject('<let name="x" type="i32" value="-2147483649"/>', "outside i32 range")
        self.reject('<let name="x" type="i64" value="-9223372036854775809"/>',
                    "outside i64 range")
        self.reject('<let name="x" type="u32" value="-1"/>', "negative literal requires")
        self.reject('<let name="x" type="u64" value="-1"/>', "negative literal requires")

    def test_signed_only_unary_minus_and_bitwise_requires_unsigned(self):
        self.reject('<let name="x" type="u64" value="1"/>'
                    '<print value="-x"/>', "unary minus requires")
        self.reject('<let name="x" type="i32" value="-1"/>'
                    '<print value="~x"/>', "bitwise NOT requires")
        self.reject('<let name="x" type="i64" value="1"/>'
                    '<print value="x &amp; 3"/>', "bitwise operations require")

    def test_zero_crossing_and_negative_widening_are_explicit(self):
        c = compile_html(program(
            '<let name="x" type="i32" value="-1"/>'
            '<let name="y" type="i64" value="i64(x)"/>'
            '<print value="y"/>'
            '<print value="u64(x)"/>'))
        self.assertIn('htmlk_from_bits_i64((uint64_t)(htmlk_v_x))', c)
        self.assertIn('((uint64_t)(htmlk_v_x))', c)

    def test_reject_signed_return_if_width_mismatch(self):
        f = function("wrong", "n:i64", "i32", '<return value="n"/>')
        self.reject('<print value="wrong(-1)"/>',
                    "expected i32 expression but got i64", f)
        f = function("wrong", "n:i32", "i64", '<return value="n"/>')
        self.reject('<print value="wrong(-1)"/>',
                    "expected i64 expression but got i32", f)

    def test_no_signed_overflow_execution_in_generated_code(self):
        c = compile_html(program(
            '<let name="x" type="i64" value="9223372036854775807"/>'
            '<print value="x + 1"/>'))
        self.assertIn('htmlk_add_i64(htmlk_v_x, INT64_C(1))', c)
        self.assertIn('htmlk_from_bits_i64((uint64_t)a + (uint64_t)b)', c)

    def test_no_boolean_to_integer_cast(self):
        for conv in ("i32", "i64", "u32", "u64"):
            self.reject(f'<print value="{conv}(1 == 1)"/>', "requires an integer")

    def test_reserved_type_names_not_function_declarations(self):
        for name in ("i32", "i64", "u32", "u64"):
            self.reject('<print>hi</print>', "reserved numeric conversion",
                        function(name, "n:i32", "i32", '<return value="n"/>'))


if __name__ == "__main__":
    unittest.main()
