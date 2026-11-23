"""M4-C2 fault escape policy: independent native GCC -O0/-O3 UBSan."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class IsolationPolicyTests(unittest.TestCase):
    def test_fault_escape_rule_and_negative_controls(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-iso-rule-") as tmp:
            for optimization in ("-O0", "-O3"):
                with self.subTest(optimization=optimization):
                    exe = Path(tmp) / ("isolation" + optimization)
                    subprocess.run(["gcc", "-std=c11", optimization,
                        "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I", str(ROOT / "boot"),
                        str(ROOT / "boot/isolation_policy.c"),
                        str(ROOT / "tests/native/test_isolation_policy.c"),
                        "-o", str(exe)], check=True, timeout=30)
                    result = subprocess.run([str(exe)], check=True,
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.stdout,
                                     "M4 C2 FAIL-CLOSED FAULT POLICY UBSAN PASS\n")

if __name__ == "__main__":
    unittest.main()
