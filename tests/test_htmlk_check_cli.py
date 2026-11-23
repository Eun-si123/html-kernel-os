"""Human/agent CLI tests: same real compiler, machine schema and fail-closed input."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/htmlk_check.py"
EXAMPLE = ROOT / "examples/human-agent-hello.html"
BAD_TAG = ('<kernel arch="x86_64">\n<onboot>\n'
           '<prnit>Hello</prnit>\n</onboot>\n</kernel>\n')


def invoke(source: Path | str, *args: str, stdin: bytes | None = None):
    return subprocess.run(
        [sys.executable, str(CLI), str(source), *args],
        input=stdin, capture_output=True, timeout=8,
    )


class HtmlkCheckTests(unittest.TestCase):
    def test_example_is_valid_for_all_three_targets(self):
        summaries = []
        for target in ("kernel", "linux", "user"):
            with self.subTest(target=target):
                result = invoke(EXAMPLE, "--target", target, "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                doc = json.loads(result.stdout)
                self.assertEqual(doc["schema_version"], 1)
                self.assertTrue(doc["ok"])
                self.assertEqual(doc["target"], target)
                self.assertEqual(doc["diagnostics"], [])
                self.assertEqual(len(doc["generated_c_sha256"]), 64)
                summaries.append(doc)
        self.assertEqual(len({s["source_sha256"] for s in summaries}), 1)
        self.assertEqual(len({s["generated_c_sha256"] for s in summaries}), 3)

    def test_typo_has_stable_code_position_and_hint(self):
        result = invoke("-", "--json", stdin=BAD_TAG.encode())
        self.assertEqual(result.returncode, 1)
        doc = json.loads(result.stdout)
        self.assertFalse(doc["ok"])
        diagnostic, = doc["diagnostics"]
        self.assertEqual(diagnostic["code"], "HK101_TAG")
        self.assertEqual((diagnostic["line"], diagnostic["column"]), (3, 1))
        self.assertIn("Did you mean <print>?", diagnostic["hint"])
        self.assertIsNone(doc["generated_c_sha256"])
        self.assertFalse(result.stderr)

    def test_human_view_has_source_and_caret(self):
        result = invoke("-", stdin=BAD_TAG.encode())
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"<prnit>Hello</prnit>", result.stderr)
        self.assertIn(b"^", result.stderr)
        self.assertIn(b"HK101_TAG", result.stderr)
        self.assertIn(b":3:1:", result.stderr)
        self.assertFalse(result.stdout)

    def test_missing_attributes_and_user_hints(self):
        source = ('<kernel><onboot><let name="x" type="u64"/>'
                  '<print value="1"/><halt/></onboot></kernel>')
        data = json.loads(invoke("-", "--json", stdin=source.encode()).stdout)
        self.assertEqual(data["diagnostics"][0]["code"], "HK102_ATTRS")
        self.assertIn("Allowed attributes", data["diagnostics"][0]["hint"])
        valid_kernel = ('<kernel><onboot><print value="1"/>'
                        '<let name="x" type="u64" value="2"/>'
                        '<halt/></onboot></kernel>')
        user = json.loads(invoke("-", "--json", "--target", "user",
                                 stdin=valid_kernel.encode()).stdout)
        self.assertEqual(user["diagnostics"][0]["code"], "HK210_USER_TARGET")
        self.assertIsNone(user["diagnostics"][0]["line"])

    def test_invalid_utf8_and_missing_file_are_machine_readable(self):
        invalid = json.loads(invoke("-", "--json", stdin=b"\xff").stdout)
        self.assertEqual(invalid["diagnostics"][0]["code"], "HK002_UTF8")
        missing = json.loads(invoke("/no/such/htmlk-file.html", "--json").stdout)
        self.assertEqual(missing["diagnostics"][0]["code"], "HK003_FILE")

    def test_oversize_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/"oversize.html"
            source.write_bytes(b"a"*131073)
            result = invoke(source, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["diagnostics"][0]["code"],
                             "HK301_BOUNDS")
            link = Path(root)/"link.html"
            link.symlink_to(EXAMPLE)
            result = invoke(link, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["ok"])
            self.assertFalse((Path(root)/"generated.c").exists())

    def test_source_is_real_native_linux_program(self):
        with tempfile.TemporaryDirectory() as root:
            c = Path(root)/"app.c"
            binary = Path(root)/"app"
            run = subprocess.run([sys.executable, str(ROOT/"compiler/htmlk.py"),
                                  str(EXAMPLE), "--target", "linux",
                                  "--out", str(c)],
                                 capture_output=True, timeout=12)
            self.assertEqual(run.returncode, 0, run.stderr)
            build = subprocess.run(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra",
                                    "-Werror", str(c), "-o", str(binary)],
                                   capture_output=True, timeout=12)
            self.assertEqual(build.returncode, 0, build.stderr)
            executed = subprocess.run([str(binary)], capture_output=True, timeout=5)
            self.assertEqual((executed.returncode, executed.stdout),
                             (0, b"3\n3\n3\n4294967296\n"))

    def test_agents_can_discover_actual_canonical_tag_contract(self):
        from compiler.language import ALLOWED, CHILDREN, REQUIRED, MAX_SOURCE_BYTES
        result = subprocess.run([sys.executable, str(CLI), "--describe", "--json"],
                                capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(set(data["tags"]), set(CHILDREN))
        self.assertEqual(data["limits"]["source_bytes"], MAX_SOURCE_BYTES)
        for tag in CHILDREN:
            self.assertEqual(set(data["tags"][tag]["attributes"]), ALLOWED[tag])
            self.assertEqual(set(data["tags"][tag]["required_attributes"]),
                             REQUIRED.get(tag, set()))
        self.assertIn("user", data["supported_targets"])
        self.assertIn("strict HTML-shaped", data["syntax"])

    def test_json_diagnostic_is_deterministic_across_runs(self):
        a = invoke("-", "--target", "user", "--json", stdin=BAD_TAG.encode())
        b = invoke("-", "--target", "user", "--json", stdin=BAD_TAG.encode())
        self.assertEqual(a.returncode, b.returncode)
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout)["diagnostics"][0]["line"], 3)

    def test_source_validity_does_not_create_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/"example.html"
            source.write_bytes(EXAMPLE.read_bytes())
            before = set(Path(root).iterdir())
            result = invoke(source, "--target", "user", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(Path(root).iterdir()), before)


if __name__ == "__main__":
    unittest.main()
