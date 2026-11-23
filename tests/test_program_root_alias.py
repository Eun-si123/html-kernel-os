"""M2-UX3: nonkernel program/main source aliases, same AST/native semantics."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compiler.htmlk import compile_html, CompileError
from compiler.language import CHILDREN, ALLOWED, parse

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "examples/human-agent-program.html"
PROGRAM = FILE.read_text(encoding="utf-8")


def kernel_equivalent(text: str) -> str:
    return (text.replace("<program>", '<kernel arch="x86_64">')
                .replace("</program>", "</kernel>")
                .replace("<main>", "<onboot>")
                .replace("</main>", "</onboot>"))


class ProgramRootAliasTests(unittest.TestCase):
    def test_canonical_ast_source_form_preserves_user_program_semantics(self):
        parsed = parse(PROGRAM)
        self.assertEqual(parsed.root_form, "program")
        self.assertEqual(parsed.statements[0].tag, "let")
        self.assertEqual(parsed.statements[-1].tag, "halt")
        self.assertIn("double", parsed.functions)
        self.assertEqual(parse(kernel_equivalent(PROGRAM)).root_form, "kernel")

    def test_linux_and_ring3_match_legacy_codegen_exactly(self):
        for target in ("linux", "user"):
            with self.subTest(target=target):
                self.assertEqual(compile_html(PROGRAM, target=target),
                                 compile_html(kernel_equivalent(PROGRAM),
                                              target=target))

    def test_kernel_rejects_program_source_before_native_codegen(self):
        with self.assertRaisesRegex(CompileError,
                                    "for Linux or Ring3 user apps"):
            compile_html(PROGRAM, target="kernel")
        self.assertIn("kernel_main", compile_html(kernel_equivalent(PROGRAM),
                                                  target="kernel"))

    def test_grammar_metadata_includes_opt_in_aliases(self):
        self.assertEqual(CHILDREN["program"], {None})
        self.assertEqual(CHILDREN["main"], {"program"})
        self.assertEqual(ALLOWED["main"], set())
        result = subprocess.run(
            [sys.executable, str(ROOT/"scripts/htmlk_check.py"),
             "--describe", "--json"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        schema = json.loads(result.stdout)
        self.assertEqual(schema["tags"]["main"]["parents"], ["program"])
        self.assertEqual(schema["tags"]["program"]["parents"], ["(document)"])
        self.assertEqual(len(schema["tags"]), 18)

    def test_mixed_pairings_and_closing_tags_are_not_accepted(self):
        for bad in (
            PROGRAM.replace("<main>", "<onboot>").replace("</main>", "</onboot>"),
            PROGRAM.replace("<program>", "<kernel>").replace("</program>", "</kernel>"),
            PROGRAM.replace("</main>", "</onboot>"),
            PROGRAM.replace("</program>", "</kernel>"),
            PROGRAM.replace("<main>", "<main><main>").replace("</main>", "</main></main>"),
            PROGRAM.replace("<program>", "<program><program>").replace("</program>",
                                                                    "</program></program>"),
        ):
            with self.subTest(source=bad[:120]):
                for target in ("linux", "user"):
                    with self.assertRaises(CompileError):
                        compile_html(bad, target=target)

    def test_invalid_attributes_and_arch_still_reject(self):
        for bad in (
            PROGRAM.replace("<program>", '<program arch="arm64">'),
            PROGRAM.replace("<main>", '<main enabled="true">'),
            PROGRAM.replace("<program>", '<program arch="x86_64" arch="x86_64">'),
            PROGRAM.replace("<main>", "<main><script></script>"),
        ):
            with self.subTest(source=bad[:80]):
                with self.assertRaises(CompileError):
                    compile_html(bad, target="user")

    def test_semantic_type_and_bounds_errors_match_legacy_source(self):
        for changed in (
            PROGRAM.replace('name="count" type="u64" value="3"',
                            'name="count" type="wat" value="3"'),
            PROGRAM.replace('value="4294967296"', 'value="18446744073709551616"'),
            PROGRAM.replace('times="3"', 'times="65"'),
        ):
            with self.subTest(source=changed[-120:]):
                for target in ("linux", "user"):
                    with self.assertRaises(CompileError):
                        compile_html(changed, target=target)

    def test_native_linux_process_executes_real_new_syntax(self):
        with tempfile.TemporaryDirectory() as td:
            c = Path(td)/"program.c"
            binary = Path(td)/"program"
            result = subprocess.run(
                [sys.executable, str(ROOT/"compiler/htmlk.py"), str(FILE),
                 "--target", "linux", "--out", str(c)],
                capture_output=True, timeout=12)
            self.assertEqual(result.returncode, 0, result.stderr)
            compiled = subprocess.run(
                ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 str(c), "-o", str(binary)], capture_output=True, timeout=15)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, timeout=5)
            self.assertEqual((ran.returncode, ran.stdout),
                             (0, b"6\n6\n6\n4294967296\n"))

    def test_user_checker_error_preserves_original_source_line_position(self):
        bad = PROGRAM.replace("<main>", "<main>\n    <prnit>oops</prnit>")
        with tempfile.TemporaryDirectory() as temp:
            f = Path(temp)/"bad.html"
            f.write_text(bad, encoding="utf-8")
            got = subprocess.run([sys.executable, str(ROOT/"scripts/htmlk_check.py"),
                                  str(f), "--target", "user", "--json"],
                                 capture_output=True, timeout=8)
            self.assertEqual(got.returncode, 1)
            doc = json.loads(got.stdout)
            self.assertEqual(doc["diagnostics"][0]["code"], "HK101_TAG")
            self.assertIsInstance(doc["diagnostics"][0]["line"], int)
            self.assertIn("<print>", doc["diagnostics"][0]["hint"])


if __name__ == "__main__":
    unittest.main()
