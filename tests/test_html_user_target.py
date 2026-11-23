"""M5-F1 shared HTML parser/source semantics targeting bounded native Ring3 HKEX."""
from __future__ import annotations
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest

from compiler.htmlk import compile_html
from compiler.language import CompileError
from scripts.build_user_image import fnv1a

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = (ROOT/'examples/user-programs/html-hello.html').read_text()


class HtmlUserTargetTests(unittest.TestCase):
    def test_same_typed_language_lowers_to_register_syscalls_without_ports(self):
        c=compile_html(EXAMPLE,target='user')
        self.assertIn('htmlk_user_main',c)
        self.assertIn('int $0x80',c)
        self.assertIn('htmlk_fn_triple',c)
        self.assertNotIn('outb',c)
        self.assertNotIn('#include <stdio.h>',c)
        self.assertIn('htmlk_user_stack_probe',c)
        self.assertEqual(compile_html(EXAMPLE,target='user'),c)
        # Other targets remain usable for the same grammar and AST.
        self.assertIn('kernel_main',compile_html(EXAMPLE,target='kernel'))
        self.assertIn('int main(void)',compile_html(EXAMPLE,target='linux'))

    def test_reject_user_only_unsupported_io_shapes(self):
        samples=[
          EXAMPLE.replace('<print value="triple(score) - 1046"/>', '<print>한글</print>'),
          EXAMPLE.replace('<print value="triple(score) - 1046"/>',
                          '<repeat times="8"><print value="1"/></repeat><print value="2"/>'),
          EXAMPLE.replace('<print value="triple(score) - 1046"/>',
                          '<repeat times="2"><print value="2"/></repeat>'),
          EXAMPLE.replace('<print value="triple(score) - 1046"/>',
                          '<let name="neg" type="i64" value="-5"/><print value="neg"/>'),
          EXAMPLE.replace('<print value="triple(score) - 1046"/>',
                          '<print value="triple(score) - 1046"/><let name="last" type="u64" value="0"/>'),
          EXAMPLE.replace('<let name="score" type="u64" value="1000"/>',
                          '<let name="score" type="wat" value="1000"/>'),
        ]
        for sample in samples:
            with self.subTest(sample=sample[-165:]):
                with self.assertRaises(CompileError):
                    compile_html(sample,target='user')

    def test_build_html_hkex_deterministic_and_header_checksum(self):
        script=ROOT/'scripts/build_html_user_image.py'
        with tempfile.TemporaryDirectory(prefix='htmlk-user-unit-') as tmp:
            a=Path(tmp)/'a.hke'; b=Path(tmp)/'b.hke'
            for output in (a,b):
                subprocess.run([sys.executable,str(script),'--source',
                                str(ROOT/'examples/user-programs/html-hello.html'),
                                '--out',str(output)],check=True,capture_output=True,timeout=30)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            image=a.read_bytes()
            self.assertEqual(image[:8],b'HKEX\x01\x20\x00\x00')
            size=int.from_bytes(image[12:16],'little')
            self.assertEqual(len(image),size+32)
            self.assertLessEqual(len(image),4096)
            self.assertEqual(int.from_bytes(image[16:20],'little'),fnv1a(image[32:]))
            edited=Path(tmp)/'changed.html'
            edited.write_text(EXAMPLE.replace('1046','1045'))
            third=Path(tmp)/'c.hke'
            subprocess.run([sys.executable,str(script),'--source',str(edited),
                            '--out',str(third)],check=True,capture_output=True,timeout=30)
            self.assertNotEqual(image,third.read_bytes())

    def test_build_rejects_bad_shape_without_artifact(self):
        script=ROOT/'scripts/build_html_user_image.py'
        with tempfile.TemporaryDirectory(prefix='htmlk-user-invalid-') as tmp:
            testpath=Path(tmp)/'invalid.html'; outfile=Path(tmp)/'invalid.hke'
            testpath.write_text(EXAMPLE.replace('<print value="triple(score) - 1046"/>',
                                             '<print>한글</print>'))
            result=subprocess.run([sys.executable,str(script),'--source',str(testpath),
                                   '--out',str(outfile)],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('user text output allows only printable ASCII',result.stderr)
            self.assertFalse(outfile.exists())
            testpath.write_text(EXAMPLE)
            oversize=Path(tmp)/'oversize.html'
            oversize.write_bytes(b'x'*131073)
            result=subprocess.run([sys.executable,str(script),'--source',str(oversize),
                                   '--out',str(outfile)],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(outfile.exists())
            link=Path(tmp)/'link.html'
            link.symlink_to(testpath)
            result=subprocess.run([sys.executable,str(script),'--source',str(link),
                                   '--out',str(outfile)],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(outfile.exists())
            # The ISO wrapper must not resolve away the symlink and bypass
            # the standalone builder's strict input-source policy.
            iso=Path(tmp)/'bad-source.iso'
            check=subprocess.run([
                sys.executable,str(ROOT/'scripts/build_boot.py'),
                '--user-app-html',str(link),'--exception-idt','--tss-ist',
                '--romfs-run-console','--out',str(iso)],
                capture_output=True,text=True,timeout=15)
            self.assertNotEqual(check.returncode,0)
            self.assertFalse(iso.exists())


if __name__=='__main__':unittest.main()
