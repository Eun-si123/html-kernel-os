"""First-class function declaration/call syntax and codegen contract."""
import unittest

from compiler.htmlk import compile_html, CompileError


def src(funcs: str, boot: str = '<print value="f(2)"/>',
        *, after: bool = False) -> str:
    onboot = f'<onboot>{boot}</onboot>'
    return f'<kernel arch="x86_64">{onboot + funcs if after else funcs + onboot}</kernel>'


def fn(name: str = "f", params: str = "x:u64", value: str = "x * 2",
       returns: str = "u64") -> str:
    return (f'<function name="{name}" params="{params}" returns="{returns}">'
            f'<return value="{value}"/></function>')


class FunctionTests(unittest.TestCase):
    def invalid(self, funcs: str, boot: str, reason: str,
                *, after: bool = False) -> None:
        with self.assertRaisesRegex(CompileError, reason):
            compile_html(src(funcs, boot, after=after))

    def test_typed_function_and_call_codegen_on_both_targets(self):
        funcs = fn("sum", "a:u64,b:u64", "a + b")
        boot = '<print value="sum(3, 4)"/>'
        for target in ("linux", "kernel"):
            with self.subTest(target=target):
                c = compile_html(src(funcs, boot), target=target)
                self.assertIn(
                    'uint64_t htmlk_fn_sum(uint64_t htmlk_v_a, uint64_t htmlk_v_b);', c
                )
                self.assertIn('uint64_t htmlk_fn_sum(', c)
                self.assertIn('htmlk_print_u64(htmlk_fn_sum(', c)
                self.assertIn('return ((uint64_t)(htmlk_v_a + htmlk_v_b));', c)

    def test_forward_and_nested_calls_and_unused_function(self):
        funcs = (
            fn("outer", "x:u64", "inner(x) + base()") +
            fn("base", "", "7") +
            fn("inner", "z:u64", "z * 2") +
            fn("unused", "", "999")
        )
        code = compile_html(src(funcs, '<print value="outer(2)"/>', after=True))
        self.assertIn('htmlk_fn_inner(htmlk_v_x)', code)
        self.assertIn('htmlk_fn_base()', code)
        self.assertIn('htmlk_fn_unused(void)', code)

    def test_calls_in_conditions_repeats_assignments(self):
        code = compile_html(src(
            fn(), '<let name="n" type="u64" value="f(1)"/>'
            '<repeat times="3"><set name="n" value="f(n)"/>'
            '<if test="f(n) == 16"><print value="n"/></if></repeat>'
        ))
        self.assertIn('htmlk_v_n = htmlk_fn_f(htmlk_v_n);', code)
        self.assertIn('if ((htmlk_fn_f(htmlk_v_n) == UINT64_C(16)))', code)

    def test_missing_and_wrong_parameters(self):
        self.invalid(fn(), '<print value="f()"/>', "expects 1 arguments")
        self.invalid(fn(), '<print value="f(1, 2)"/>', "expects 1 arguments")
        self.invalid(fn(), '<print value="unknown(2)"/>', "undefined function")
        self.invalid(fn(), '<print value="f(x=2)"/>', "unsupported function call")
        self.invalid(fn(), '<print value="f(1)(2)"/>', "unsupported function call")
        self.invalid(fn(), '<print value="f(1 == 1)"/>',
                     "function arguments must be u64")

    def test_invalid_function_signatures_and_duplicates(self):
        self.invalid(fn(params="z:i16"), '<print>ok</print>', "bad typed parameter")
        self.invalid(fn(params="7x:u64"), '<print>ok</print>', "bad typed parameter")
        self.invalid(fn(params="x:u64,x:u64"), '<print>ok</print>', "duplicate parameter")
        self.invalid(fn(params="x:u64,y:u64,z:u64,v:u64,w:u64"),
                     '<print>ok</print>', "parameters exceed limit")
        self.invalid(fn(returns="void"), '<print>ok</print>', 'only returns=')
        self.invalid(fn()+fn(), '<print value="f(1)"/>', "already defined")
        self.invalid(fn(name="for"), '<print>ok</print>', "invalid variable name")

    def test_function_body_is_exactly_one_pure_return(self):
        self.invalid('<function name="f" params="" returns="u64"/>',
                     '<print>ok</print>', "must end with")
        self.invalid('<function name="f" params="" returns="u64">'
                     '<return value="1"/><return value="2"/></function>',
                     '<print>ok</print>', "unreachable")
        self.invalid('<function name="f" params="" returns="u64">'
                     '<print>bad</print></function>', '<print>ok</print>', "not allowed")
        self.invalid('<function name="f" params="" returns="u64">'
                     '<return value="1">TEXT</return></function>',
                     '<print>ok</print>', "text is only")
        self.invalid(fn(value="z"), '<print>ok</print>', "undefined variable")

    def test_direct_and_indirect_recursion_rejected(self):
        self.invalid(fn(value="f(x)"), '<print value="f(2)"/>', "recursive function")
        self.invalid(fn("f","x:u64","g(x)")+fn("g","y:u64","f(y)"),
                     '<print value="f(2)"/>', "recursive function")
        # Cycles in unreferenced functions must still fail compilation.
        self.invalid(fn(value="f(x)"), '<print>ok</print>', "recursive function")

    def test_deep_and_expensive_non_recursive_calls_rejected(self):
        chain = ''.join(fn(f"f{i}", "", f"f{i+1}()") for i in range(8))
        chain += fn("f8", "", "1")
        self.invalid(chain, '<print value="f0()"/>', "call depth exceeds")
        # Exponentially expanding acyclic graph; the runtime estimate must reject.
        graph = ''.join(fn(f"f{i}", "",
                           " + ".join([f"f{i+1}()"] * 10))
                        for i in range(6))
        graph += fn("f6", "", "1")
        self.invalid(graph, '<print value="f0()"/>', "work limit exceeded")
        # Single function call in nested repeats must respect the work budget.
        heavy = ''.join(fn(f"g{i}", "",
                           " + ".join([f"g{i+1}()"] * 4))
                        for i in range(5)) + fn("g5", "", "1")
        self.invalid(heavy, '<repeat times="64"><print value="g0()"/></repeat>',
                     "expanded function work budget")

    def test_no_functions_keeps_existing_code_unchanged(self):
        code = compile_html(src('', '<print>hello</print><halt/>'))
        self.assertNotIn('htmlk_fn_', code)
        self.assertIn('void kernel_main(void)', code)


if __name__ == "__main__":
    unittest.main()
