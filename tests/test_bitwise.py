"""Bitwise unsigned operations and bounded shift contract."""
import unittest
from compiler.htmlk import compile_html, CompileError


def program(body, f=""):
    return f'<kernel arch="x86_64">{f}<onboot><print>bits</print>{body}</onboot></kernel>'


class BitwiseTests(unittest.TestCase):
    def reject(self, body, pattern):
        for target in ("linux", "kernel"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, pattern):
                    compile_html(program(body), target=target)

    def test_u32_mask_xor_or_and(self):
        c = compile_html(program(
            '<let name="mask" type="u32" value="5"/>'
            '<print value="(mask &amp; 3) | (mask ^ 7)"/>'))
        self.assertIn('htmlk_v_mask & UINT32_C(3)', c)
        self.assertIn('htmlk_v_mask ^ UINT32_C(7)', c)
        self.assertIn(' | ', c)

    def test_u64_mask_and_invert(self):
        c = compile_html(program(
            '<let name="x" type="u64" value="4"/>'
            '<print value="~x"/>'
            '<print value="x ^ 2"/>'))
        self.assertIn('((uint64_t)(~htmlk_v_x))', c)
        self.assertIn('((uint64_t)(htmlk_v_x ^ UINT64_C(2)))', c)

    def test_u32_shift_left_right_and_large_amount(self):
        c = compile_html(program(
            '<let name="x" type="u32" value="1"/>'
            '<print value="x &lt;&lt; 31"/>'
            '<print value="x &lt;&lt; 32"/>'
            '<print value="x &gt;&gt; 32"/>'))
        self.assertIn('htmlk_shl_u32(htmlk_v_x, UINT32_C(31))', c)
        self.assertIn('htmlk_shl_u32(htmlk_v_x, UINT32_C(32))', c)
        self.assertIn('htmlk_shr_u32(htmlk_v_x, UINT32_C(32))', c)
        self.assertIn('shift >= 32 ? (uint32_t)0', c)

    def test_u64_shift_boundary_and_wrap(self):
        c = compile_html(program(
            '<let name="x" type="u64" value="1"/>'
            '<print value="x &lt;&lt; 63"/>'
            '<print value="x &lt;&lt; 64"/>'))
        self.assertIn('htmlk_shl_u64(htmlk_v_x, UINT64_C(63))', c)
        self.assertIn('shift >= 64 ? (uint64_t)0', c)

    def test_shift_argument_must_be_matching_width_or_literal(self):
        self.reject('<let name="x" type="u32" value="1"/>'
                    '<let name="y" type="u64" value="2"/>'
                    '<print value="x &lt;&lt; y"/>', 'cannot mix')
        self.reject('<let name="x" type="u32" value="1"/>'
                    '<print value="x &lt;&lt; -1"/>', 'negative literal requires')
        self.reject('<let name="x" type="u32" value="1"/>'
                    '<print value="x &lt;&lt; 4294967296"/>', 'outside u32 range')

    def test_bitwise_rejects_signed(self):
        for expr in ("x & 1", "x | 1", "x ^ 1", "~x", "x << 1", "x >> 1"):
            with self.subTest(expr=expr):
                self.reject('<let name="x" type="i32" value="-1"/>'
                            f'<print value="{expr}"/>'.replace('&', '&amp;')
                            .replace('<<','&lt;&lt;').replace('>>','&gt;&gt;'),
                            "bitwise")

    def test_bitwise_all_literal_default_u64(self):
        c = compile_html(program(
            '<print value="1 &amp; 3"/>'
            '<print value="5 ^ 2"/>'
            '<print value="1 &lt;&lt; 63"/>'))
        self.assertIn('((uint64_t)(UINT64_C(1) & UINT64_C(3)))', c)
        self.assertIn('((uint64_t)(UINT64_C(5) ^ UINT64_C(2)))', c)
        self.assertIn('htmlk_shl_u64(UINT64_C(1), UINT64_C(63))', c)

    def test_safe_narrowing_requires_explicit_cast(self):
        c = compile_html(program(
            '<let name="x" type="i32" value="-1"/>'
            '<let name="mask" type="u32" value="u32(x) &amp; 255"/>'
            '<print value="mask"/>'))
        self.assertIn('((uint32_t)(htmlk_v_x)) & UINT32_C(255)', c)

    def test_shift_right_always_logical_on_unsigned(self):
        c = compile_html(program(
            '<print value="u32(4294967295) &gt;&gt; 1"/>'))
        self.assertIn('htmlk_shr_u32', c)
        self.assertIn('a >> shift', c)

    def test_boolean_or_is_not_bitwise_or(self):
        c = compile_html(program(
            '<if test="1 == 1 or 2 == 3"><print>good</print></if>'))
        self.assertIn(' || ', c)
        self.reject('<print value="(1 == 1) | 3"/>', "integer|bitwise")

    def test_unsupported_ops_remain_rejected(self):
        for expr in ("1 // 2", "2 ** 3", "3 @ 2"):
            with self.subTest(expr=expr):
                self.reject(f'<print value="{expr}"/>', "unsupported")
        # Integer / and % are supported; literal-zero operands still fail.
        self.reject('<print value="1 / 0"/>', "zero literal")

    def test_boolean_operators_must_use_comparisons(self):
        self.reject('<if test="1 and 2"><print>x</print></if>', "boolean operators require")
        self.reject('<if test="~1"><print>x</print></if>', "expected boolean")


if __name__ == "__main__":
    unittest.main()
