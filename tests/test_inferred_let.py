"""Optional local type annotation uses the existing typed expression engine."""
import unittest
from compiler.htmlk import compile_html
from compiler.language import CompileError
from compiler.diagnostics import describe

def wrap(body, fn=""):
    return f"<kernel>{fn}<onboot>{body}<print>ok</print><halt/></onboot></kernel>"

class InferredLetTests(unittest.TestCase):
    def test_equivalent_explicit_types_all_targets(self):
        pairs = [
            ("10", "u64"), ("-4", "i64"), ("2 + 3 * 4", "u64"),
            ("u32(8)", "u32"), ("i32(-8)", "i32"),
            ("base + 2", "u32"), ("items[0]", "i32"), ("f(base)", "u32"),
            ("18446744073709551615", "u64"), ("-9223372036854775808", "i64"),
        ]
        pre = '<let name="base" type="u32" value="1"/><array name="items" type="i32" length="2"/>'
        f = '<function name="f" params="x:u32" returns="u32"><return value="x"/></function>'
        for target in ("kernel", "linux", "user"):
            for expr, typ in pairs:
                with self.subTest(target=target, expr=expr):
                    self.assertEqual(compile_html(wrap(pre+f'<let name="v" value="{expr}"/>', f), target=target),
                                     compile_html(wrap(pre+f'<let name="v" type="{typ}" value="{expr}"/>', f), target=target))
    def test_function_scope_and_shadowing(self):
        f = '<function name="f" params="x:u32" returns="u32"><if test="x == 2"><let name="x" value="x + 1"/><return value="x"/></if><let name="v" value="x"/><return value="v"/></function>'
        explicit=f.replace('name="x" value=', 'name="x" type="u32" value=').replace('name="v" value=', 'name="v" type="u32" value=')
        self.assertEqual(compile_html(wrap('', f)),compile_html(wrap('', explicit)))
    def test_rejections_preserved(self):
        for body in (
            '<let name="v" value="1 == 1"/>',
            '<let name="v" value="v"/>',
            '<let name="v" value="18446744073709551616"/>',
            '<let name="v" value="-9223372036854775809"/>',
            '<let name="v" value="1"/><set name="v" value="i32(1)"/>',
            '<let name="v" value="u32(1) + u64(1)"/>',
            '<let name="v" type="" value="1"/>',
            '<let name="v"/>',
            '<let name="v" value="1"/><let name="v" value="2"/>',
            '<let name="v" value="1" typo="x"/>',
            '<repeat times="1"><let name="v" value="1"/></repeat><print value="v"/>',
        ):
            for target in ("kernel", "linux", "user"):
                with self.subTest(body=body, target=target), self.assertRaises(CompileError):
                    compile_html(wrap(body),target=target)
    def test_public_metadata_and_ring3_signed_inference(self):
        self.assertEqual(describe()["tags"]["let"]["required_attributes"],["name","value"])
        self.assertIn("htmlk_user_call(UINT64_C(4)", compile_html('<program><main><let name="v" value="-1"/><print value="v"/><halt/></main></program>',target="user"))
