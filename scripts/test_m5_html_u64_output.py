#!/usr/bin/env python3
"""M5-F5: real BIOS QEMU full u64 HTML user report and guarded legacy limit."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from test_boot import ROOT, boot
from test_m5_html_user_text import build as build_iso
from test_m5_interactive_run import exercise, BASE, HTML
from test_m5_user_timeout import CPU, SPIN_TRACE
from test_m5_user_loader import make_iso as legacy_iso
from build_user_image import build as build_assembly

APP=ROOT/'examples/user-programs/html-u64-report.html'
LARGE=b'M5_C_USER_VALUE=4294967296\n'
MAX=b'M5_C_USER_VALUE=18446744073709551615\n'
STATUS=b'M5_RUN_EXIT_CODE=7\n'


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-f5-u64-') as d:
        work=Path(d)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        kernel=ROOT/'examples/kernel.html'
        root=work/'romfs';shutil.copytree(ROOT/'examples/romfs',root)
        for name,source in (
            ('ten-thousand.hke','report-ten-thousand.S'),
            ('bad-budget.hke','bad-report-budget.S')):
            build_assembly(ROOT/'examples/user-programs'/source,root/name)
        iso=work/'u64.iso'
        build_iso(kernel,APP,iso,work,cache,root)
        for attempt in range(3):
            cmds=[(b'run /apps/hello.hke\r',STATUS),
                  (b'run /ten-thousand.hke\r',b'M5_C_USER_VALUE=10000\n'),
                  (b'run /bad-budget.hke\r',b'M5_ERR_USER_SYSCALL\n'),
                  (b'run /apps/spin.hke\r',b'M5_ERR_USER_TIMEOUT\n'),
                  (b'help\r',b'M5_HELP help ls cat /path run /path exit'),
                  (b'run /apps/hello.hke\r',STATUS),
                  (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)]
            log,uart=exercise(iso,cmds,HTML,cpu=CPU)
            assert log.startswith(BASE) and log.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert log.count(LARGE)==4,(attempt,log)
            assert log.count(MAX)==2,(attempt,log)
            assert log.count(STATUS)==2,(attempt,log)
            assert log.count(b'M5_C_USER_VALUE=10000\n')==1,(attempt,log)
            assert log.count(b'M5_C_USER_VALUE=777\n')==8,(attempt,log)
            assert log.count(b'M5_ERR_USER_SYSCALL\n')==1,(attempt,log)
            assert log.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED\n')==1,(attempt,log)
            assert log.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,(attempt,log)
            assert log.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==3,(attempt,log)
            for marker,count in ((LARGE,4),(MAX,2),(STATUS,2),
                                 (b'M5_C_USER_VALUE=10000\n',1)):
                assert uart.count(marker)==count,(attempt,marker,uart)
            assert b'M4_UNKNOWN_SYSCALL_REJECTED' not in log
            print(f'M5-F5 QEMU {attempt+1}/3: 64-BIT TEXT, EXIT7, 10K REPORT, 9TH REJECT, TRUE IRQ TIMEOUT, RERUN PASS',flush=True)
        modified=work/'modified-user.html'
        previous=APP.read_text()
        assert previous.count('4294967296')==1
        assert previous.count('18446744073709551615')==1
        modified.write_text(previous.replace('4294967296','4294967297').replace(
            '18446744073709551615','18446744073709551614'))
        changed=work/'changed.iso'
        build_iso(kernel,modified,changed,work,cache,root)
        altered_large=b'M5_C_USER_VALUE=4294967297\n'
        altered_max=b'M5_C_USER_VALUE=18446744073709551614\n'
        log,uart=exercise(changed,[
            (b'run /apps/hello.hke\r',STATUS),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert changed.read_bytes()!=iso.read_bytes()
        assert log.count(altered_large)==2 and log.count(altered_max)==1
        assert LARGE not in log and MAX not in log
        assert altered_large in uart and altered_max in uart
        print('M5-F5 SOURCE MUTATION CHANGES ACTUAL ROMFS ISO, CPU OUTPUT AND UART U64 BYTES',flush=True)
        final_budget=work/'eight-u64.html'
        final_budget.write_text('''<kernel arch="x86_64"><onboot>
<repeat times="7"><print value="18446744073709551615"/></repeat>
<print value="18446744073709551615"/>
<halt code="7"/>
</onboot></kernel>''')
        eight_iso=work/'eight.iso'
        build_iso(kernel,final_budget,eight_iso,work,cache,root)
        log,uart=exercise(eight_iso,[
            (b'run /apps/hello.hke\r',STATUS),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert log.count(MAX)==8 and uart.count(MAX)==8,(log,uart)
        assert log.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==1
        print('M5-F5 8 FULL UINT64_MAX REPORTS ACTUALLY EXECUTE INSIDE 8-CALL BUDGET',flush=True)
        above=work/'out-of-range.html'
        above.write_text(previous.replace('18446744073709551615',
                                          '18446744073709551616'))
        denied=work/'denied.iso'
        command=[sys.executable,str(ROOT/'scripts/build_boot.py'),
                 '--source',str(kernel),'--user-app-html',str(above),
                 '--exception-idt','--tss-ist','--romfs-run-console',
                 '--user-fault-recover','--user-timeout','--out',str(denied)]
        outcome=subprocess.run(command,capture_output=True,text=True,timeout=35)
        assert outcome.returncode!=0 and not denied.exists(),outcome.stderr
        print('M5-F5 HTML NUMBER ABOVE UINT64_MAX REJECTED BEFORE ISO OUTPUT',flush=True)
        legacy=work/'legacy-10k.iso'
        legacy_iso(kernel,legacy,work,cache,
                   '--user-app-source',str(ROOT/'examples/user-programs/report-ten-thousand.S'))
        code,raw=boot(legacy,timeout=18)
        assert code==53,(code,raw)
        assert 'M4_UNKNOWN_SYSCALL_REJECTED' in raw,raw
        assert 'M5_C_USER_VALUE=10000' not in raw
        print('M5-F5 LEGACY M5-C1 >9999 SYSCALL STILL FAIL-STOPS WITHOUT HTML OPT-IN',flush=True)
    print('M5-F5 REAL NATIVE UINT64 REPORT ABI, 8-CALL CAP AND LEGACY DENIAL ACCEPTANCE PASS')

if __name__=='__main__':main()
