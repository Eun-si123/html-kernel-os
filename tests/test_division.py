"""M2 integer division/remainder: strict typing, defined edge cases and faults."""
import unittest

from compiler.htmlk import CompileError, compile_html


def source(body: str, functions: str = "") -> str:
    return f'<kernel arch="x86_64">{functions}<onboot><print>math</print>{body}</onboot></kernel>'


class DivisionTests(unittest.TestCase):
    def reject(self, body: str, reason: str, functions: str = "") -> None:
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, reason):
                    compile_html(source(body, functions), target=target)

    def test_all_widths_have_checked_divide_and_modulo(self):
        body = ''.join(
            f'<print value="{kind}(19) / {kind}(5)"/>'
            f'<print value="{kind}(19) % {kind}(5)"/>'
            for kind in ("u32", "u64", "i32", "i64")
        )
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                generated = compile_html(source(body), target=target)
                for kind in ("u32", "u64", "i32", "i64"):
                    self.assertIn(f"htmlk_div_{kind}(", generated)
                    self.assertIn(f"htmlk_mod_{kind}(", generated)
                self.assertIn("HTMLK_DIVIDE_BY_ZERO", generated)
                self.assertIn("if (b == 0) htmlk_divide_by_zero();", generated)
                self.assertIn("INT64_MIN && b == (int64_t)-1", generated)
                self.assertIn("INT32_MIN && b == (int32_t)-1", generated)

    def test_comparisons_functions_and_nested_expressions(self):
        fn = ('<function name="f" params="x:i32,y:i32" returns="i32">'
              '<let name="result" type="i32" value="x / y"/>'
              '<return value="result % i32(4)"/></function>')
        body = ('<if test="f(i32(-21), i32(5)) == 0">'
                '<print>match</print></if>'
                '<print value="(u64(20) / 2) + (u64(9) % 2)"/>')
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                generated = compile_html(source(body, fn), target=target)
                self.assertIn("htmlk_fn_f(", generated)
                self.assertIn("htmlk_div_i32(", generated)
                self.assertIn("htmlk_mod_u64(", generated)

    def test_reject_literal_zero_and_unsupported_floor_division(self):
        self.reject('<print value="5 / 0"/>', "zero literal")
        self.reject('<print value="5 % 0"/>', "zero literal")
        self.reject('<print value="i32(5) / i32(0)"/>', "zero literal")
        self.reject('<print value="u64(5) / (+0)"/>', "zero literal")
        self.reject('<print value="i64(-5) % -0"/>', "zero literal")
        self.reject('<print value="5 // 2"/>', "unsupported binary operator")
        self.reject('<print value="i32(-1) / u32(2)"/>', "cannot mix")
        self.reject('<print value="i64(-1) % u64(2)"/>', "cannot mix")
        self.reject('<print value="u32(1) / i32(-1)"/>', "cannot mix")
        self.reject('<print value="5 / 0.0"/>', "unsupported|expected")
        self.reject('<print value="5 / missing"/>', "undefined variable")

    def test_runtime_zero_allowed_for_late_guard(self):
        # The compiler cannot know the denominator at runtime; the generated
        # helper must trap it rather than silently produce a result.
        body = '<let name="x" type="u64" value="0"/><print value="5 / x"/>'
        generated = compile_html(source(body), target="linux")
        self.assertIn("htmlk_div_u64(", generated)
        self.assertIn("exit(65);", generated)
        kernel = compile_html(source(body))
        self.assertIn("io_outb(0xf4, 0x11)", kernel)
        self.assertNotIn("exit(65)", kernel)

    def test_u64_and_signed_minimum_boundaries(self):
        body = ('<print value="u64(18446744073709551615) / u64(3)"/>'
                '<print value="i64(-9223372036854775808) / i64(-1)"/>'
                '<print value="i64(-9223372036854775808) % i64(-1)"/>'
                '<print value="i32(-2147483648) / i32(-1)"/>')
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                code = compile_html(source(body), target=target)
                self.assertIn("htmlk_div_i64", code)
                self.assertIn("htmlk_mod_i64", code)
                self.assertIn("htmlk_div_i32", code)


if __name__ == "__main__":
    unittest.main()
