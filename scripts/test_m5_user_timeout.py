#!/usr/bin/env python3
"""M5-E2 true x2APIC CPL3 non-yielding app timeout -> live COM1 shell."""
from __future__ import annotations
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML, BASE, APP_TRACE
from build_user_image import build as build_user_image

CPU='qemu64,+x2apic'
TIMER=b'M5_E2_X2APIC_TIMER_READY\n'
SPIN_TRACE=(b'M5_RUN_START /apps/spin.hke\n'
            b'M5_C_ROMFS_PROGRAM_LOADED\nM5_C_USER_PAGES_READY\n'+TIMER+
            b'M5_E2_REAL_USER_IRQ_1\nM5_E2_REAL_USER_IRQ_LIMIT\n'
            b'M5_E2_CPL3_TIMEOUT\nM5_E2_TIMEOUT_FRAMES_RECLAIMED\n'
            b'M5_ERR_USER_TIMEOUT\nM5_PROMPT> ')
GOOD_TRACE=APP_TRACE.replace(b'M5_C_USER_PAGES_READY\n',
                             b'M5_C_USER_PAGES_READY\n'+TIMER)


def build(source:Path,out:Path,work:Path,cache:Path,*args:str)->None:
    cmd=[sys.executable,str(ROOT/'scripts/build_boot.py'),
         '--source',str(source),'--out',str(out),'--work-dir',str(work),
         '--cache-dir',str(cache), '--exception-idt','--tss-ist',
         '--romfs-run-console','--user-fault-recover','--user-timeout',
         '--test-exit',*args]
    completed=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=150)
    assert completed.returncode==0 and 'ROMFS_CONTENT_SHA256=' in completed.stdout,(
        completed.stdout,completed.stderr)


def negative_cpu(iso:Path,expected:bytes,*,cpu:str,masked:bool=False)->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e2-negative-') as tmp:
        log=Path(tmp)/'debug.log'
        cmd=['qemu-system-x86_64','-M','q35','-m','256M',
             '-cpu',cpu,'-cdrom',str(iso),'-boot','d',
             '-display','none','-monitor','none','-net','none',
             '-serial','stdio','-debugcon',f'file:{log}',
             '-global','isa-debugcon.iobase=0xe9',
             '-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-no-reboot']
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        def current()->bytes:return log.read_bytes() if log.is_file() else b''
        try:
            beginning=time.monotonic()
            while BASE not in current():
                if time.monotonic()-beginning>17 or p.poll() is not None:
                    raise AssertionError(('no prompt',p.returncode,current()))
                time.sleep(.02)
            assert current()==BASE,current()
            assert p.stdin is not None
            for ch in b'run /apps/spin.hke\r':
                p.stdin.write(bytes((ch,)))
                p.stdin.flush()
                time.sleep(.008)
            if not masked:
                _,stderr=p.communicate(timeout=12)
                result=current()
                assert p.returncode==57,(p.returncode,result,stderr)
                assert expected in result,(expected,result)
                assert b'M5_E2_REAL_USER_IRQ_1' not in result
                assert b'M5_ERR_USER_TIMEOUT' not in result
                assert HTML not in result
            else:
                start=time.monotonic()
                while TIMER not in current() and time.monotonic()-start<8:
                    assert p.poll() is None,(p.returncode,current())
                    time.sleep(.015)
                assert TIMER in current(),current()
                time.sleep(1.4)
                result=current()
                assert p.poll() is None,(p.returncode,result)
                assert result.count(TIMER)==1,result
                assert b'M5_E2_REAL_USER_IRQ_1' not in result
                assert b'M5_E2_CPL3_TIMEOUT' not in result
                assert b'M5_ERR_USER_TIMEOUT' not in result
                assert result.count(b'M5_PROMPT> ')==1,result
                assert HTML not in result
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=4)


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e2-') as tmp:
        work=Path(tmp)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        source=ROOT/'examples/kernel.html'
        original=work/'original.iso'
        build(source,original,work,cache)
        for attempt in range(3):
            operations=[(b'run /apps/spin.hke\r',SPIN_TRACE),
                        (b'run /apps/hello.hke\r',GOOD_TRACE),
                        (b'run /apps/fault-ud.hke\r',b'M5_ERR_USER_FAULT'),
                        (b'run /apps/hello.hke\r',GOOD_TRACE),
                        (b'run /apps/spin.hke\r',SPIN_TRACE),
                        (b'run /apps/hello.hke\r',GOOD_TRACE),
                        (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)]
            guest,uart=exercise(original,operations,HTML,cpu=CPU)
            assert guest.startswith(BASE) and guest.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert guest.count(SPIN_TRACE)==2,(attempt,guest)
            assert guest.count(GOOD_TRACE)==3,(attempt,guest)
            assert guest.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED')==2
            assert guest.count(b'M5_C_USER_FRAMES_RECLAIMED')==3
            assert guest.count(b'M5_E_FAULT_FRAMES_RECLAIMED')==1
            assert guest.count(b'M5_E2_REAL_USER_IRQ_1')==2
            assert guest.count(b'M5_E2_REAL_USER_IRQ_LIMIT')==2
            assert uart.count(b'M5_ERR_USER_TIMEOUT')==2
            assert uart.count(b'M5_C_USER_VALUE=2026')==3
        print('M5-E2 THREE ACTUAL QEMU BOOTS: 2 INFINITE RING3 LOOPS -> CPU IRQ -> PROMPT -> VALID RUN PASS')
        idle,_=exercise(original,[],HTML,idle=True,cpu=CPU)
        assert idle==BASE
        print('M5-E2 IDLE KERNEL CONSOLE WITHOUT UART INPUT DOES NOT START TIMER/USER')
        changed_html=work/'source-changed.html'
        old_html=source.read_text()
        assert old_html.count('Hello from HTML Kernel!')==1
        changed_html.write_text(old_html.replace('Hello from HTML Kernel!',
                                                 'M5-E2 NEW NATIVE HTML!'))
        new_html=HTML.replace(b'Hello from HTML Kernel!',b'M5-E2 NEW NATIVE HTML!')
        html_iso=work/'html-changed.iso'
        build(changed_html,html_iso,work,cache)
        new_trace,_=exercise(html_iso,[
            (b'run /apps/spin.hke\r',SPIN_TRACE),
            (b'run /apps/hello.hke\r',GOOD_TRACE),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+new_html)],new_html,cpu=CPU)
        assert html_iso.read_bytes()!=original.read_bytes()
        assert new_trace.endswith(b'M5_CONSOLE_EXIT\n'+new_html)
        print('M5-E2 CHANGED HTML -> DIFFERENT ISO -> NEW GENUINE NATIVE GUEST OUTPUT')
        changed_app=work/'user-changed.S'
        hello_source=(ROOT/'examples/user-programs/hello.S').read_text()
        assert hello_source.count('$2026')==1
        changed_app.write_text(hello_source.replace('$2026','$2027'))
        new_app_iso=work/'app-changed.iso'
        build(source,new_app_iso,work,cache,'--user-app-source',str(changed_app))
        new_good=GOOD_TRACE.replace(b'M5_C_USER_VALUE=2026',b'M5_C_USER_VALUE=2027')
        app_trace,uart=exercise(new_app_iso,[
            (b'run /apps/spin.hke\r',SPIN_TRACE),
            (b'run /apps/hello.hke\r',new_good),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,cpu=CPU)
        assert new_app_iso.read_bytes()!=original.read_bytes()
        assert b'M5_C_USER_VALUE=2027' in uart
        assert b'M5_C_USER_VALUE=2026' not in app_trace
        print('M5-E2 CHANGED SEPARATE USER PROGRAM -> DISTINCT ISO AND CPL3 OUTPUT')
        negative_cpu(original,b'M5_E2_X2APIC_REQUIRED',cpu='qemu64,-x2apic')
        print('M5-E2 UNSUPPORTED x2APIC CPU REJECTED; NO FAKE IRQ SUCCESS')
        masked_iso=work/'masked.iso'
        build(source,masked_iso,work,cache,'--user-timeout-mask')
        negative_cpu(masked_iso,TIMER,cpu=CPU,masked=True)
        print('M5-E2 MASKED REAL TIMER -> INFINITE CPL3 APP CANNOT RETURN; HOST TIMEOUT NEGATIVE PASS')
        # Integration gap: merged M5-E1 #77/#78 and M5-E2 #79 passed in
        # isolation. Prove one REAL guest can handle x2APIC timeout,
        # CPU faults and illegal syscall *while the timer is configured*,
        # then still run an independent valid HKEX app in the same shell.
        extra_root=work/'romfs-with-safe-app'
        shutil.copytree(ROOT/'examples/romfs',extra_root)
        valid_hkex=build_user_image(ROOT/'examples/user-programs/hello.S',
                                    extra_root/'safe.hke')
        assert len(valid_hkex)>40
        (extra_root/'corrupt.hke').write_bytes(
            valid_hkex[:40]+bytes((valid_hkex[40]^1,))+valid_hkex[41:])
        safe_trace=GOOD_TRACE.replace(b'/apps/hello.hke',b'/safe.hke')
        cpu_faults=(
            (b'run /apps/fault-io.hke\r',b'M5_E_USER_GP_0'),
            (b'run /apps/fault-pf.hke\r',b'M5_E_USER_PF_5'),
            (b'run /apps/fault-ro.hke\r',b'M5_E_USER_PF_7'),
            (b'run /apps/fault-ud.hke\r',b'M5_E_USER_UD'),
        )
        for invalid_program in ('bad-syscall.S','bad-argument.S'):
            iso=work/('integrated-'+invalid_program+'.iso')
            build(source,iso,work,cache,
                  '--romfs-root',str(extra_root),
                  '--user-app-source',str(ROOT/'examples/user-programs'/invalid_program))
            commands=[(b'run /apps/spin.hke\r',SPIN_TRACE),
                      (b'run /corrupt.hke\r',b'M5_ERR_BAD_EXEC'),
                      (b'run /missing.hke\r',b'M5_ERR_NOT_FOUND'),
                      (b'run /../escape.hke\r',b'M5_ERR_INVALID_PATH')]
            for command,marker in cpu_faults:
                commands.append((command,b'M5_ERR_USER_FAULT'))
            commands.extend([
                (b'run /safe.hke\r',safe_trace),
                (b'run /apps/hello.hke\r',b'M5_ERR_USER_SYSCALL'),
                (b'run /safe.hke\r',safe_trace),
                (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML),
            ])
            log,uart=exercise(iso,commands,HTML,cpu=CPU)
            assert log.startswith(BASE) and log.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
            assert log.count(SPIN_TRACE)==1
            assert log.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED')==1
            assert log.count(b'M5_E_FAULT_FRAMES_RECLAIMED')==4
            assert log.count(b'M5_ERR_USER_FAULT')==4
            for _,marker in cpu_faults:
                assert log.count(marker)==1,(marker,log)
            assert log.count(b'M5_E_BAD_SYSCALL_FRAMES_RECLAIMED')==1
            assert log.count(b'M5_ERR_USER_SYSCALL')==1
            assert log.count(b'M5_ERR_BAD_EXEC')==1
            assert log.count(b'M5_ERR_NOT_FOUND')==1
            assert log.count(b'M5_ERR_INVALID_PATH')==1
            # Eight genuine user launches (1 spin, 4 CPU faults,
            # 1 invalid syscall, 2 healthy HKEX); invalid files/paths
            # must never enable x2APIC or install a new task image.
            assert log.count(TIMER)==8,(log.count(TIMER),log)
            assert log.count(b'M5_RUN_START ') == 8
            assert log.count(safe_trace)==2
            assert log.count(b'M5_C_USER_FRAMES_RECLAIMED')==2
            assert uart.count(b'M5_ERR_USER_TIMEOUT')==1
            assert uart.count(b'M5_ERR_USER_FAULT')==4
            assert uart.count(b'M5_ERR_USER_SYSCALL')==1
            assert uart.count(b'M5_C_USER_VALUE=2026')==2
        print('M5-E3-A REAL QEMU: TIMER + FOUR CPU FAULTS + TWO SYSCALL REJECTIONS + CORRUPT HKEX/PATH DENIAL + RE-RUN PASS')

        for opts in (
            ('--user-timeout',),
            ('--user-timeout','--exception-idt','--tss-ist','--romfs-run-console'),
            ('--user-timeout-mask',),
            ('--user-timeout-mask','--user-timeout','--user-fault-recover',
             '--exception-idt','--tss-ist','--romfs-run-console'),
            ('--user-timeout','--user-fault-recover','--exception-idt',
             '--tss-ist','--romfs-run-console','--user-preempt-probe'),
        ):
            target=work/'invalid.iso'
            reject=subprocess.run([sys.executable,str(ROOT/'scripts/build_boot.py'),
                                   '--out',str(target),*opts],
                                  capture_output=True,text=True,timeout=12)
            assert reject.returncode!=0 and not target.exists(),(opts,reject.stderr)
        print('M5-E2 INCOMPATIBLE/INCOMPLETE FLAG COMBINATIONS REJECTED')
    print('M5-E2 REAL INTERRUPT-DRIVEN RING3 TIMEOUT + CONSOLE SURVIVAL ACCEPTANCE PASS')

if __name__=='__main__': main()
