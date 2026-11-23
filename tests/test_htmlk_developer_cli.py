"""CLI real native code execution and failure-path proof for human/agent users."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compiler.htmlk import compile_html
from scripts.build_html_user_image import build as build_user_image

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "scripts/htmlk.py"
EXAMPLE = ROOT / "examples/human-agent-hello.html"
EXPECTED = b"3\n3\n3\n4294967296\n"


def cli(*args: str | Path):
    return subprocess.run([sys.executable, str(CMD), *map(str, args)],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=45)


class HtmlkDeveloperCliTests(unittest.TestCase):
    def test_run_real_linux_native_output(self):
        result = cli("run", EXAMPLE)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, EXPECTED, b""))

    def test_run_json_stable_source_semantics(self):
        result = cli("run", EXAMPLE, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "linux")
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["stdout"].encode(), EXPECTED)
        self.assertEqual(data["stderr"], "")
        self.assertEqual(data["generated_c_sha256"], hashlib.sha256(
            compile_html(EXAMPLE.read_text(), target="linux").encode()).hexdigest())

    def test_build_linux_produces_real_elf_and_reproducible_output(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "program"
            result = cli("build", EXAMPLE, "--target", "linux",
                         "--out", artifact, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["sha256"], hashlib.sha256(
                artifact.read_bytes()).hexdigest())
            self.assertEqual(artifact.read_bytes()[:4], b"\x7fELF")
            self.assertTrue(artifact.stat().st_mode & 0o111)
            executed = subprocess.run([str(artifact)], capture_output=True, timeout=5)
            self.assertEqual((executed.returncode, executed.stdout), (0, EXPECTED))

    def test_build_user_matches_canonical_hkex(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "program.hke"
            result = cli("build", EXAMPLE, "--target", "user",
                         "--out", artifact, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["target"], "user")
            self.assertEqual(data["bytes"], len(artifact.read_bytes()))
            self.assertEqual(artifact.read_bytes()[:4], b"HKEX")
            reference = Path(temp) / "reference.hke"
            build_user_image(EXAMPLE, reference)
            self.assertEqual(reference.read_bytes(), artifact.read_bytes())

    def test_build_requires_explicit_force_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "program"
            dest.write_bytes(b"KEEP_EXISTING_DATA")
            original = cli("build", EXAMPLE, "--out", dest)
            self.assertEqual(original.returncode, 1)
            self.assertEqual(dest.read_bytes(), b"KEEP_EXISTING_DATA")
            forced = cli("build", EXAMPLE, "--out", dest, "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(dest.read_bytes()[:4], b"\x7fELF")

    def test_symlink_output_is_never_overwritten_even_with_force(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "user-data"
            target.write_bytes(b"IMPORTANT")
            symlink = Path(temp) / "app"
            symlink.symlink_to(target)
            result = cli("build", EXAMPLE, "--out", symlink, "--force")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(target.read_bytes(), b"IMPORTANT")
            self.assertTrue(symlink.is_symlink())

    def test_kernel_build_and_run_are_never_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "kernel"
            result = cli("build", EXAMPLE, "--target", "kernel",
                         "--out", dest, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(dest.exists())
            self.assertIn("never execute privileged kernels",
                          json.loads(result.stdout)["diagnostics"][0]["message"])
        self.assertEqual(cli("run", EXAMPLE, "--target", "kernel").returncode, 2)

    def test_invalid_source_produces_no_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "invalid.html"
            bad.write_text("<kernel><onboot><unknown/></onboot></kernel>")
            dest = Path(temp) / "missing-parent" / "program"
            result = cli("build", bad, "--out", dest, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(dest.parent.exists())
            data = json.loads(result.stdout)
            self.assertFalse(data["ok"])
            self.assertEqual(data["diagnostics"][0]["code"], "HK101_TAG")

    def test_empty_missing_symlink_source_and_invalid_utf8_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for name, content in (("badutf8.html", b"\xff\xfe"),
                                  ("too-big.html", b"X"*131073),
                                  ("empty.html", b"")):
                source = base / name
                source.write_bytes(content)
                result = cli("run", source, "--json")
                self.assertEqual(result.returncode, 1)
                self.assertFalse(json.loads(result.stdout)["ok"])
            link = base / "link.html"
            link.symlink_to(EXAMPLE)
            self.assertEqual(cli("run", link).returncode, 1)
            self.assertEqual(cli("run", base/"not-found.html").returncode, 1)

    def test_check_and_describe_reuse_existing_json_checker(self):
        direct = subprocess.run([sys.executable, str(ROOT/"scripts/htmlk_check.py"),
                                 str(EXAMPLE), "--target", "user", "--json"],
                                capture_output=True, timeout=6)
        via_cli = cli("check", EXAMPLE, "--target", "user", "--json")
        self.assertEqual(via_cli.stdout, direct.stdout)
        self.assertEqual(via_cli.returncode, direct.returncode)
        schema = json.loads(cli("describe", "--json").stdout)
        self.assertEqual(schema["schema_version"], 1)
        self.assertIn("kernel", schema["tags"])

    def test_concurrent_build_same_output_never_clobbers(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "concurrent-app"
            processes = [subprocess.Popen([
                sys.executable, str(CMD), "build", str(EXAMPLE),
                "--target", "linux", "--out", str(destination),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
            statuses = [proc.communicate(timeout=20) for proc in processes]
            self.assertEqual(sorted(proc.returncode for proc in processes), [0, 1],
                             statuses)
            self.assertTrue(destination.read_bytes().startswith(b"\x7fELF"))
            result = subprocess.run([str(destination)], capture_output=True, timeout=5)
            self.assertEqual((result.returncode, result.stdout), (0, EXPECTED))

    def test_build_changed_html_changes_real_native_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"changed.html"
            original = EXAMPLE.read_text()
            source.write_text(original.replace('name="count" type="u64" value="3"',
                                               'name="count" type="u64" value="5"'))
            result = cli("run", source, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["stdout"],
                             "5\n5\n5\n4294967296\n")
            a = Path(temp)/"a.hke"
            b = Path(temp)/"b.hke"
            self.assertEqual(cli("build", EXAMPLE, "--target", "user",
                                 "--out", a).returncode, 0)
            self.assertEqual(cli("build", source, "--target", "user",
                                 "--out", b).returncode, 0)
            self.assertNotEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
