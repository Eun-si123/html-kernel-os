"""M5-C1 hosted runner nm retry must NOT weaken ELF symbol assertions."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
# The runtime script uses top-level imports; restore discovery sys.path
# immediately or `scripts/test_*.py` can shadow `tests/test_*.py` modules.
script_dir = str(ROOT / 'scripts')
sys.path.insert(0, script_dir)
try:
    from test_m5_user_loader import checked_nm_symbols  # noqa: E402
finally:
    sys.path.remove(script_dir)


class NmRetryTests(unittest.TestCase):
    def test_one_stall_retries_exact_same_elf_and_validates_output(self):
        calls=[]
        def runner(args, **kw):
            calls.append((tuple(args),kw))
            if len(calls)==1:
                raise subprocess.TimeoutExpired(args,kw['timeout'])
            return subprocess.CompletedProcess(args,0,stdout='000001 T htmlk_entry\n',stderr='')
        content=checked_nm_symbols(Path('/tmp/small.elf'),runner=runner)
        self.assertIn('htmlk_entry',content)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0],calls[1])
        self.assertEqual(calls[0][0],('nm','/tmp/small.elf'))
        self.assertEqual(calls[0][1]['timeout'],20)
        self.assertTrue(calls[0][1]['check'])

    def test_two_timeouts_fail_closed(self):
        attempts=[]
        def runner(args,**kw):
            attempts.append(args)
            raise subprocess.TimeoutExpired(args,kw['timeout'])
        with self.assertRaisesRegex(AssertionError,'timed out twice'):
            checked_nm_symbols(Path('/tmp/stalled.elf'),runner=runner)
        self.assertEqual(len(attempts),2)

    def test_nm_error_is_never_suppressed_or_retried(self):
        attempts=[]
        def runner(args,**kw):
            attempts.append(args)
            raise subprocess.CalledProcessError(1,args,output='')
        with self.assertRaises(subprocess.CalledProcessError):
            checked_nm_symbols(Path('/tmp/broken.elf'),runner=runner)
        self.assertEqual(len(attempts),1)

    def test_real_gcc_elf_object_contains_expected_symbol(self):
        with tempfile.TemporaryDirectory(prefix='htmlk-nm-symbol-test-') as t:
            dest=Path(t)
            source=dest/'proof.c'
            obj=dest/'proof.o'
            source.write_text('int htmlk_nm_real_proof(void) { return 42; }\n')
            subprocess.run(['gcc','-std=c11','-c',str(source),'-o',str(obj)],
                           check=True,capture_output=True,timeout=20)
            content=checked_nm_symbols(obj)
            self.assertIn('htmlk_nm_real_proof',content)
            self.assertNotIn('htmlk_m4_user_code_begin',content)

if __name__=='__main__':
    unittest.main()
