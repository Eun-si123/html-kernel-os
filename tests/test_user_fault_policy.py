"""M5-E1 host UBSan guard for real CPL3 CPU exception recovery frames."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class UserFaultPolicyTests(unittest.TestCase):
    def test_native_guard_optimizations_and_negatives(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-m5-e1-guard-") as temp:
            for opt in ("-O0","-O3"):
                target=Path(temp)/(f"guard-{opt}")
                subprocess.run(["gcc", "-std=c11", opt,
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-Wall", "-Wextra", "-Werror", "-I", str(ROOT/"boot"),
                    str(ROOT/"boot/user_fault_policy.c"),
                    str(ROOT/"tests/native/test_user_fault_policy.c"),
                    "-o", str(target)],check=True,timeout=25)
                out=subprocess.run([str(target)],capture_output=True,text=True,
                                   check=True,timeout=10)
                self.assertEqual(out.stdout,
                    "M5-E1 USER EXCEPTION FRAME/CR3/SEL/ERR GUARDS PASS\n")

if __name__=='__main__':unittest.main()
