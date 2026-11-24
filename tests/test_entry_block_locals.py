"""Lexical entrypoint scopes and C identifier hygiene across targets."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from compiler.htmlk import compile_html
from compiler.language import CompileError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "examples/block-locals.html").read_text()

def wrap(body):
    return '<kernel><onboot>'+body+'<print>done</print><halt/></onboot></kernel>'

class EntryBlockTests(unittest.TestCase):
    def test_native_linux_original_and_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            for initial, expected in [(3,b"26\n9\n12\n"),(5,b"30\n15\n12\n")]:
                source=SOURCE.replace('name="loop_0" value="3"',f'name="loop_0" value="{initial}"')
                c=Path(td)/"app.c"; exe=Path(td)/"app"
                c.write_text(compile_html(source,target="linux"))
                for opt in ("-O0","-O2"):
                    subprocess.run(["gcc",opt,"-std=c11","-Wall","-Wextra","-Werror","-fsanitize=undefined",str(c),"-o",str(exe)],check=True,capture_output=True,timeout=15)
                    self.assertEqual(subprocess.check_output([str(exe)],timeout=5),expected)
    def test_preexisting_loop_counter_collision(self):
        source = '<program><main><let name="loop_0" value="10"/><repeat times="2"><set name="loop_0" value="loop_0 + 1"/></repeat><print value="loop_0"/><halt/></main></program>'
        with tempfile.TemporaryDirectory() as td:
            c=Path(td)/"collision.c"; exe=Path(td)/"collision"
            c.write_text(compile_html(source,target="linux"))
            subprocess.run(["gcc","-std=c11","-Wall","-Wextra","-Werror",str(c),"-o",str(exe)],check=True,capture_output=True,timeout=15)
            self.assertEqual(subprocess.check_output([str(exe)],timeout=5),b"12\n")
    def test_scope_negative_cases_all_targets(self):
        cases = [
            ('<if test="1 == 1"><let name="x" value="1"/></if><print value="x"/>',"undefined variable"),
            ('<repeat times="0"><let name="x" value="x"/></repeat>',"undefined variable"),
            ('<while max="0" test="x == 1"><let name="x" value="1"/></while>',"undefined variable"),
            ('<if test="1 == 1"><let name="x" value="1"/><else><set name="x" value="2"/></else></if>',"undefined variable"),
            ('<if test="1 == 1"><let name="x" value="1"/><array name="x" type="u64" length="1"/></if>',"already declared"),
            ('<repeat times="1"><array name="a" type="u64" length="2"/></repeat><store name="a" index="0" value="1"/>',"undefined array"),
            ('<let name="x" value="1"/><if test="x == 1"><let name="x" value="u32(x)"/><set name="x" value="u64(1)"/></if>',"expected u32"),
        ]
        for target in ("kernel","linux","user"):
            for body, reason in cases:
                with self.subTest(target=target,body=body),self.assertRaisesRegex(CompileError,reason):
                    compile_html(wrap(body),target=target)
    def test_hygienic_symbols_and_static_user_budget(self):
        c=compile_html(SOURCE,target="user")
        self.assertIn("htmlk_v_loop_0",c)
        self.assertIn("htmlk_loop_0",c)
        self.assertIn("htmlk_v_repeat_adjust_0",c)
        self.assertIn("htmlk_repeat_adjust_0",c)
        self.assertIn("htmlk_v_print_u64",c)
        self.assertIn("htmlk_block_",c)
        with self.assertRaisesRegex(CompileError,"8 syscall reports"):
            compile_html(wrap('<repeat times="8"><let name="x" value="1"/><print value="x"/></repeat>'),target="user")
