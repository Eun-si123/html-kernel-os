"""M2 bounded while: runtime guard, type checking, scoping and work budgets."""
import unittest

from compiler.htmlk import CompileError, compile_html


def kernel(body: str, functions: str = "") -> str:
    return f'<kernel arch="x86_64">{functions}<onboot><print>ready</print>{body}</onboot></kernel>'


class WhileTests(unittest.TestCase):
    def compile_both(self, body: str, functions: str = "") -> None:
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                generated = compile_html(kernel(body, functions), target=target)
                self.assertTrue("htmlk_loop_" in generated or "htmlk_repeat_" in generated,
                                "no generated bounded loop for " + target)

    def reject(self, body: str, reason: str, functions: str = "") -> None:
        for target in ("kernel", "linux"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CompileError, reason):
                    compile_html(kernel(body, functions), target=target)

    def test_dynamic_condition_and_hard_cap(self):
        body = ('<let name="i" type="u64" value="0"/>'
                '<while test="i &lt; 3" max="5">'
                '<print value="i"/><set name="i" value="i + 1"/>'
                '</while>')
        for target in ("kernel", "linux"):
            code = compile_html(kernel(body), target=target)
            self.assertIn("htmlk_loop_0 < UINT64_C(5) && ((htmlk_i < UINT64_C(3)))", code)
            self.assertIn("htmlk_i =", code)

    def test_zero_cap_still_validates_test_and_body(self):
        self.compile_both('<while test="1 == 1" max="0"><break/></while>')
        self.reject('<while test="missing == 1" max="0"><break/></while>', "undefined variable")
        self.reject('<while test="1 == 1" max="0"><set name="missing" value="1"/></while>',
                    "undefined variable")

    def test_nested_loops_and_control_flow(self):
        body = ('<repeat times="2"><while test="1 == 1" max="3">'
                '<if test="1 == 2"><continue/><else><break/></else></if>'
                '</while></repeat>')
        self.compile_both(body)
        self.compile_both('<while test="1 == 1" max="2">'
                          '<repeat times="2"><break/></repeat><continue/></while>')

    def test_scoped_function_while_shadowing_and_calls(self):
        functions = (
            '<function name="f" params="x:u32" returns="u32">'
            '<let name="y" type="u32" value="x"/>'
            '<while test="y &lt; u32(5)" max="4">'
            '<let name="temp" type="u32" value="y"/>'
            '<set name="y" value="temp + 1"/>'
            '</while><return value="y"/>'
            '</function>'
        )
        self.compile_both('<print value="f(u32(1))"/>', functions)
        self.reject('<print value="f(u32(1))"/>', "undefined variable",
                    functions.replace('<return value="y"/>', '<return value="temp"/>'))
        self.reject('<print value="f(u32(1))"/>', "unreachable",
                    functions.replace('<set name="y" value="temp + 1"/>',
                                      '<continue/><set name="y" value="temp + 1"/>'))

    def test_reject_bad_bounds_attributes_and_types(self):
        self.reject('<while test="1 == 1"><print>x</print></while>', "invalid attributes")
        self.reject('<while max="2"><print>x</print></while>', "invalid attributes")
        self.reject('<while test="1 == 1" max="65"><print>x</print></while>', "while max")
        self.reject('<while test="1 == 1" max="-1"><print>x</print></while>', "while max")
        self.reject('<while test="1 == 1" max="2" extra="x"><print>x</print></while>',
                    "invalid attributes")
        self.reject('<while test="42" max="2"><print>x</print></while>', "expected boolean")
        self.reject('<while test="1 == 1" max="2">'
                    '<let name="local" type="u64" value="1"/></while>',
                    "only supported inside functions")
        self.reject('<break/>', "requires|not allowed")

    def test_static_work_and_output_budget(self):
        # Even a run-time condition that may be false cannot bypass worst-case budgets.
        self.reject('<while test="1 == 0" max="64">'
                    '<repeat times="64"><repeat times="64">'
                    '<set name="x" value="1"/>'
                    '</repeat></repeat></while>', "estimated work exceeds")
        self.reject('<while test="1 == 0" max="64">'
                    '<repeat times="64"><print>lots of output</print></repeat>'
                    '</while>', "estimated output exceeds")

    def test_function_test_calls_are_counted_every_possible_iteration(self):
        functions = (
            '<function name="heavy" params="x:u64" returns="u64">'
            '<let name="v" type="u64" value="x"/>'
            '<repeat times="64"><set name="v" value="v + 1"/></repeat>'
            '<return value="v"/></function>'
        )
        body = ('<repeat times="6">'
                '<while test="heavy(0) == 64" max="64"><break/></while>'
                '</repeat>')
        self.reject(body, "expanded function work budget exceeded", functions)


if __name__ == "__main__":
    unittest.main()
