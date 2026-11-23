"""M4-D pure CPU user frame/fault policy at -O0/-O3 + UBSan."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class M4UserPreemptPolicy(unittest.TestCase):
    def test_host_cpu_frame_and_fault_validation(self):
        with tempfile.TemporaryDirectory(prefix="htmlk-m4d-policy-") as tmp:
            for opt in ("-O0","-O3"):
                with self.subTest(opt=opt):
                    out=Path(tmp)/("policy"+opt)
                    subprocess.run(["gcc","-std=c11",opt,"-Wall","-Wextra",
                        "-Werror","-fsanitize=undefined",
                        "-fno-sanitize-recover=all",
                        "-I",str(ROOT/"boot"),
                        str(ROOT/"boot/user_preempt_policy.c"),
                        str(ROOT/"tests/native/test_user_preempt_policy.c"),
                        "-o",str(out)],check=True,timeout=30)
                    result=subprocess.run([str(out)],capture_output=True,
                        text=True,check=True,timeout=10)
                    self.assertEqual(result.stdout,
                        "M4-D REAL CPL3 FRAME/FALLBACK PREDICATES UBSAN PASS\n")

if __name__=="__main__":
    unittest.main()
