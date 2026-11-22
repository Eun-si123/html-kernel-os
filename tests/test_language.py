"""M2 language-core contracts: positive codegen and source rejection."""
import unittest

from compiler.htmlk import compile_html, CompileError
from compiler.language import MAX_OUTPUT_BYTES, UINT64_MAX


def wrap(body: str) -> str:
    return f'<kernel arch="x86_64"><onboot>{body}</onboot></kernel>'


class LanguageTests(unittest.TestCase):
    def assert_invalid(self, body: str, reason: str) -> None:
        with self.assertRaisesRegex(CompileError, reason):
            compile_html(wrap(body))

    def test_checked_codegen_variables_loop_and_branch(self):
        src = (
            '<let name="score" type="u64" value="2 + 3 * 4"/>'
            '<repeat times="3"><print value="score"/>'
            '<set name="score" value="score + 2"/></repeat>'
            '<if test="score == 20"><print>condition PASS</print></if><halt/>'
        )
        generated = compile_html(wrap(src))
        self.assertIn('uint64_t htmlk_score =', generated)
        self.assertIn('htmlk_score =', generated)
        self.assertIn('htmlk_print_u64(htmlk_score);', generated)
        self.assertIn('for (uint64_t htmlk_loop_0', generated)
        self.assertIn('if ((htmlk_score == UINT64_C(20)))', generated)

    def test_html_attribute_entity_and_boolean_comparison(self):
        source = '<let name="x" type="u64" value="2"/><if test="x &gt; 1 and x &lt; 5"><print>yes</print></if>'
        result = compile_html(wrap(source))
        self.assertIn('htmlk_x > UINT64_C(1)', result)
        self.assertIn('&&', result)

    def test_unicode_print_and_u64_boundary(self):
        src = f'<let name="v" type="u64" value="{UINT64_MAX}"/><print value="v"/><print>안녕</print>'
        c = compile_html(wrap(src))
        self.assertIn(f'UINT64_C({UINT64_MAX})', c)
        self.assertIn('0xec, 0x95, 0x88', c)

    def test_reject_undeclared_and_redefined_variables(self):
        self.assert_invalid('<print value="missing"/>', "undefined variable")
        self.assert_invalid('<set name="missing" value="1"/><print>x</print>', "undefined variable")
        self.assert_invalid('<let name="x" type="u64" value="1"/>'
                            '<let name="x" type="u64" value="2"/><print>x</print>',
                            "already declared")
        self.assert_invalid('<let name="x" type="u64" value="x + 1"/><print>x</print>', "undefined variable")

    def test_reject_wrong_types_and_identifiers(self):
        self.assert_invalid('<let name="x" type="i16" value="2"/><print>x</print>', "only type=")
        for name in ("hello-world", "7x", "for", "x;evil", "한글"):
            with self.subTest(name=name):
                self.assert_invalid(f'<let name="{name}" type="u64" value="2"/><print>x</print>',
                                    "invalid variable name")
        self.assert_invalid('<let name="x" type="u64" value="1 == 1"/><print>x</print>',
                            "expected number")
        self.assert_invalid('<if test="42"><print>x</print></if>', "expected boolean")

    def test_reject_injected_and_unsupported_expressions(self):
        for expr in ("__import__('os').system('id')", "x[0]", "1 / 0",
                     "1 << 1.5", "(1, 2)", "2 ** 2000", "True", "1 if 2 else 3",
                     "1 < 2 < 3"):
            with self.subTest(expr=expr):
                self.assert_invalid(f'<print value="{expr}"/>',
                                    "unsupported|integer literal|expected|undefined")
        self.assert_invalid(f'<print value="{UINT64_MAX + 1}"/>', "outside u64")

    def test_reject_bad_nesting_and_attributes(self):
        self.assert_invalid('<repeat times="2"><let name="x" type="u64" value="1"/></repeat><print>x</print>',
                            "only supported inside functions")
        self.assert_invalid('<let name="x" type="u64" value="1" extra="bad"/><print>x</print>',
                            "invalid attributes")
        self.assert_invalid('<let name="x" name="y" type="u64" value="1"/><print>x</print>',
                            "duplicate attributes")
        self.assert_invalid('<print value="2">text</print>', "cannot contain text")
        self.assert_invalid('<print>x</print><if test="2 == 2"><halt/></if>',
                            "not allowed")
        self.assert_invalid('<print>x</print><halt/><print>later</print>', "after <halt")

    def test_reject_out_of_range_and_runaway_loops(self):
        for count in ("65", "-1", "1.5", "99999999"):
            with self.subTest(count=count):
                self.assert_invalid(f'<repeat times="{count}"><print>x</print></repeat>',
                                    "repeat times")
        self.assert_invalid('<repeat times="64"><print>' + "a" * 300 +
                            '</print></repeat>', "estimated output exceeds")
        self.assert_invalid('<let name="i" type="u64" value="0"/>'
                            + '<repeat times="64">' * 3
                            + '<set name="i" value="i + 1"/>'
                            + '</repeat>' * 3 + '<print value="i"/>',
                            "estimated work exceeds")
        with self.assertRaisesRegex(CompileError, "source exceeds"):
            compile_html(wrap('<print>' + 'A' * 131072 + '</print>'))

    def test_comparison_diagnostics_have_line_location(self):
        with self.assertRaisesRegex(CompileError, r"line 2, column 1: undefined variable"):
            compile_html('<kernel><onboot>\n<print value="unknown"/>\n</onboot></kernel>')

    def test_unused_decl_is_valid_and_unknown_declarations_fail(self):
        compiled = compile_html(wrap('<let name="unused" type="u64" value="7"/><print>ok</print>'))
        self.assertIn('(void)htmlk_unused;', compiled)
        with self.assertRaises(CompileError):
            compile_html(wrap('<print>x</print><!something>'))

    def test_duplicate_root_missing_boot_comments(self):
        self.assert_invalid('<print>x</print><kernel/>', "not allowed")
        ok = compile_html(wrap('<!-- a comment --><print>yes</print>'))
        self.assertIn("0x79, 0x65, 0x73", ok)
        self.assert_invalid('<print>x<!--bad--></print>', "comments")
        with self.assertRaises(CompileError):
            compile_html('<!DOCTYPE html>' + wrap('<print>x</print>'))


if __name__ == "__main__":
    unittest.main()
