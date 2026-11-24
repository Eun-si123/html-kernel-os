"""Explicit reusable source fragments: no imports, same typed compiler."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from compiler.htmlk import compile_html
from compiler.language import CompileError, MAX_SOURCE_BYTES
from scripts.htmlk_bundle import bundle
from tests.test_htmlk_developer_cli import cli

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "examples/libraries-app.html"
LIB = ROOT / "examples/libraries/math.html"


class BundleTests(unittest.TestCase):
    def test_same_source_same_native_artifacts_and_multiple_libraries(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            a,b = d/"a.html",d/"b.html"
            for out in (a,b):
                result=cli("bundle",APP,"--library",LIB,"--target","user","--out",out,"--json")
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout)["sha256"],hashlib.sha256(out.read_bytes()).hexdigest())
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(cli("run",a).stdout,b"25\n")
            self.assertEqual(cli("run",APP).returncode,1)
            for source, dest in ((a,d/"a.hke"),(b,d/"b.hke")):
                self.assertEqual(cli("build",source,"--target","user","--out",dest).returncode,0)
            self.assertEqual((d/"a.hke").read_bytes(),(d/"b.hke").read_bytes())
        f='<function name="f" params="x:u64" returns="u64"><return value="g(x)"/></function>'
        g='<function name="g" params="x:u64" returns="u64"><return value="x + 1"/></function>'
        src='<kernel><onboot><print value="f(1)"/><halt/></onboot></kernel>'
        self.assertIn("htmlk_fn_g",compile_html(bundle(src,[f,g],target="kernel")))

    def test_exact_root_insertion_and_invalid_fragments(self):
        source=APP.read_text()
        lib=LIB.read_text()
        for prefix in ("","<!-- <program> fake -->\n","<!-- x -->\r\n","<!-- x\u2028y -->\n"):
            text=prefix+source.replace("<program>",'<PROGRAM arch="x86_64">').replace("</program>","</PROGRAM>")
            actual=bundle(text,[lib],target="user")
            self.assertTrue(actual.startswith(prefix+'<PROGRAM arch="x86_64">\n'))
            self.assertEqual(actual.replace("\n"+lib+"\n","",1),text)
        for fragments in ([],[lib]*9,[""],[lib,lib],["<onboot><print>x</print></onboot>"],
                          ["</kernel><kernel>"+lib],["<import path='/etc/passwd'/>"],
                          [lib+"<!--"],["<print>bad</print>"],["x"*MAX_SOURCE_BYTES]):
            with self.subTest(fragment=str(fragments)[:80]),self.assertRaises(CompileError):
                bundle(source,fragments,target="user")
        with self.assertRaises(CompileError):
            bundle(source,[lib],target="kernel")
        with self.assertRaisesRegex(CompileError,"recursive"):
            bundle(source,[lib.replace("square(x) + square(y)","sum_squares(x, y)")],target="user")

    def test_fail_closed_cli_and_never_clobber(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            dest=root/"bundle.html"
            dest.write_bytes(b"KEEP")
            self.assertNotEqual(cli("bundle",APP,"--library",LIB,"--out",dest).returncode,0)
            self.assertEqual(dest.read_bytes(),b"KEEP")
            link=root/"link.html"
            link.symlink_to(LIB)
            missing=root/"missing.html"
            for library in (link,missing,"-"):
                self.assertNotEqual(cli("bundle",APP,"--library",library,"--out",missing).returncode,0)
                self.assertFalse(missing.exists())
            outlink=root/"outlink"
            outlink.symlink_to(dest)
            self.assertNotEqual(cli("bundle",APP,"--library",LIB,"--out",outlink).returncode,0)
            self.assertEqual(dest.read_bytes(),b"KEEP")
