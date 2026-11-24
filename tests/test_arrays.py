"""M2 bounded native arrays: scoped, typed and safe indexed access."""
import unittest

from compiler.htmlk import CompileError, compile_html


def wrap(body, func=""):
    return f'<kernel arch="x86_64">{func}<onboot><print>arrays</print>{body}</onboot></kernel>'


class ArrayTests(unittest.TestCase):
    def reject(self, body, reason, func=""):
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, reason):
                    compile_html(wrap(body, func), target=target)

    def test_typed_load_store_and_runtime_index_guard_both_targets(self):
        text = (
            '<array name="a" type="u32" length="3"/>'
            '<let name="index" type="u64" value="1"/>'
            '<store name="a" index="index" value="u32(25)"/>'
            '<print value="a[index] + u32(5)"/>')
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                c = compile_html(wrap(text), target=target)
                self.assertIn("uint32_t htmlk_v_a[3] = {0};", c)
                self.assertIn("htmlk_v_a[htmlk_checked_index(", c)
                self.assertIn("if (index >= length) htmlk_array_bounds_fault();", c)
                self.assertIn("UINT64_C(3)", c)
                self.assertIn("HTMLK_ARRAY_BOUNDS", c)
                if target == "kernel":
                    self.assertIn("io_outb(0xf4, 0x12)", c)
                else:
                    self.assertIn("exit(66)", c)

    def test_function_scopes_and_arrays_reinitialised(self):
        func = ('<function name="f" params="n:u64" returns="u64">'
                '<array name="a" type="i64" length="2"/>'
                '<store name="a" index="0" value="i64(-5)"/>'
                '<if test="n == 2">'
                '<array name="a" type="u64" length="1"/>'
                '<store name="a" index="0" value="n"/>'
                '<return value="a[0]"/></if>'
                '<return value="u64(a[0])"/></function>')
        code = compile_html(wrap('<print value="f(2)"/>', func), target="linux")
        self.assertIn("int64_t htmlk_local_f_0[2]", code)
        self.assertIn("uint64_t htmlk_local_f_1[1]", code)
        self.assertIn("htmlk_checked_index", code)

    def test_reject_out_of_bounds_compile_time(self):
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a[2]"/>', "out of bounds")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a[u32(2)]"/>', "out of bounds")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<store name="a" index="3" value="1"/>', "out of bounds")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a[-1]"/>', "array index must")

    def test_reject_unchecked_array_escape_and_unsupported_index_syntax(self):
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a"/>', "requires an indexed element")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a[0:1]"/>', "unsupported expression syntax")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a[0][0]"/>', "only a declared array")
        self.reject('<print value="b[0]"/>', "undefined array")
        self.reject('<let name="x" type="u64" value="2"/>'
                    '<print value="x[0]"/>', "undefined array")

    def test_reject_bad_arrays_and_type_mismatches(self):
        self.reject('<array name="a" type="u64" length="0"/>', "length must")
        self.reject('<array name="a" type="u64" length="65"/>', "length must")
        self.reject('<array name="a" type="float" length="2"/>', "array type")
        self.reject('<array name="a" type="u64" length="2" extra="x"/>',
                    "invalid attributes")
        self.reject('<array name="a" type="u64" length="1"/>'
                    '<array name="a" type="u32" length="1"/>', "already declared")
        self.reject('<array name="a" type="u32" length="1"/>'
                    '<store name="a" index="0" value="u64(3)"/>', "expected u32")
        self.reject('<store name="missing" index="0" value="1"/>', "undefined array")
        self.reject('<array name="a" type="u32" length="1"/>'
                    '<let name="x" type="i64" value="-1"/>'
                    '<store name="a" index="x" value="1"/>', "array index must")
        self.reject('<array name="a" type="u64" length="1"/>'
                    '<set name="a" value="1"/>', "requires an indexed element")
        self.reject('<let name="a" type="u64" value="1"/>'
                    '<store name="a" index="0" value="1"/>', "undefined array")

    def test_reject_array_count_limit(self):
        self.reject(''.join(f'<array name="a{i}" type="u64" length="1"/>'
                            for i in range(17)), "at most 16")

    def test_builtin_synthetic_escape_rejected(self):
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a.__class__"/>', "unsupported expression")
        self.reject('<array name="a" type="u64" length="2"/>'
                    '<print value="a.__getitem__(1)"/>', "unsupported function call")


if __name__ == "__main__":
    unittest.main()
