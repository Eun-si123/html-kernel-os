#!/usr/bin/env python3
"""Real BIOS QEMU: UART commands trigger repeatable ROMFS-backed CPL3 execution."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from test_boot import ROOT, SUCCESS_EXIT
from build_user_image import build as build_program

HTML=b'Hello from HTML Kernel!\nNative code, not a browser.\n'
READY=b'M3_TSS_IST_READY\nM3_IDT_READY\nM5_D_SHELL_READY\nM5_PROMPT> '
USER=(b'M5_D_RUN_BEGIN /apps/hello.hke\nM5_C_ROMFS_PROGRAM_LOADED\n'
      b'M5_C_USER_PAGES_READY\nM5_C_RING3_STACK_OK\nM5_C_USER_VALUE=2026\n'
      b'M5_C_RING3_EXIT_OK\nM5_C_USER_FRAMES_RECLAIMED\nM5_D_RUN_END\n')


def build(source:Path, iso:Path, work:Path, cache:Path, *extra:str)->None:
    args=[sys.executable,str(ROOT/'scripts/build_boot.py'),'--source',str(source),
          '--out',str(iso),'--cache-dir',str(cache),'--work-dir',str(work),
          '--romfs-shell','--test-exit',*extra]
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=180)
    if result.returncode:
        raise AssertionError(f'M5-D build failed:\n{result.stdout}\n{result.stderr}')
    assert 'ROMFS_CONTENT_SHA256=' in result.stdout


def execute(iso:Path,commands:list[tuple[bytes,bytes]],*,expected_exit:int=SUCCESS_EXIT,
            idle:bool=False)->tuple[bytes,bytes]:
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-d-uart-') as temp:
        trace=Path(temp)/'debugcon.log'
        cmd=['qemu-system-x86_64','-M','q35','-m','256M','-cdrom',str(iso),
             '-boot','d','-display','none','-monitor','none','-net','none',
             '-serial','stdio','-debugcon','file:'+str(trace),
             '-global','isa-debugcon.iobase=0xe9',
             '-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-no-reboot']
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        def seen():return trace.read_bytes() if trace.is_file() else b''
        def until(marker:bytes,before:int=0,deadline:float=16)->bytes:
            start=time.monotonic()
            while time.monotonic()-start<deadline:
                data=seen()
                if marker in data[before:]:return data
                if p.poll() is not None:
                    raise AssertionError((marker,p.returncode,data))
                time.sleep(.025)
            raise AssertionError((marker,seen()))
        try:
            assert until(READY)==READY
            if idle:
                time.sleep(.6)
                assert p.poll() is None
                assert seen()==READY,seen()
                return seen(),b''
            for command, expected in commands:
                before=len(seen())
                for byte in command:
                    assert p.stdin is not None
                    p.stdin.write(bytes((byte,)))
                    p.stdin.flush()
                    time.sleep(.009) # 16550 FIFO is finite; pace real UART input
                until(expected,before)
            stdout,stderr=p.communicate(timeout=8)
            if p.returncode!=expected_exit:
                raise AssertionError((p.returncode,expected_exit,seen(),stderr))
            result=seen()
            assert b'M5_CONSOLE_FATAL' not in result
            return result,stdout
        finally:
            if p.poll() is None:
                p.kill();p.communicate(timeout=4)


def main():
    with tempfile.TemporaryDirectory(prefix='htmlk-m5-d-') as temp:
        work=Path(temp)
        cache=Path(os.getenv('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        source=ROOT/'examples/kernel.html'
        original=work/'native-shell.iso'
        build(source,original,work,cache)
        commands=[
            (b'help\r',b'M5_HELP help ls cat /path run /apps/hello.hke exit'),
            (b'ls\r',b'M5_FILE /welcome.txt'),
            (b'cat /welcome.txt\r',b'M5_CAT_END'),
            (b'cat /apps/hello.hke\r',b'M5_ERR_BINARY_UNSUPPORTED'),
            (b'run /apps/hello.hke\r',b'M5_D_RUN_END'),
            (b'run /missing.hke\r',b'M5_ERR_NOT_EXECUTABLE'),
            (b'run /../bad\r',b'M5_ERR_INVALID_PATH'),
            (b'nonesuch\r',b'M5_ERR_UNKNOWN_COMMAND'),
            (b'x'*96+b'\r',b'M5_ERR_INVALID_LINE'),
            (b'run /apps/hello.hke\r',b'M5_D_RUN_END'),
            (b'exit\r',b'M5_CONSOLE_EXIT'),
        ]
        log,serial=execute(original,commands)
        assert log.startswith(READY)
        assert log.count(USER)==2,log
        assert log.endswith(b'M5_CONSOLE_EXIT\n'+HTML),log
        assert log.count(b'M5_ERR_INVALID_LINE')==1
        assert b'M5_C_USER_VALUE=2026' in serial
        assert serial.count(b'M5_D_RUN_END')==2
        print('M5-D TWO LIVE UART RUN COMMANDS + REAL REUSABLE RING3 + MEMORY RECLAIM PASS')
        paused,_=execute(original,[],idle=True)
        assert paused==READY
        print('M5-D IDLE ORACLE: WITHOUT ACTUAL UART BYTES NO PROGRAM/HTML EXECUTES')

        updated_source=source.read_text()
        assert updated_source.count('Hello from HTML Kernel!')==1
        changed_html=work/'modified.html'
        changed_html.write_text(updated_source.replace('Hello from HTML Kernel!',
                                                       'M5-D HTML WAS RECOMPILED!'))
        changed_iso=work/'changed-html.iso'
        build(changed_html,changed_iso,work,cache)
        data,_=execute(changed_iso,[(b'run /apps/hello.hke\r',b'M5_D_RUN_END'),
                                    (b'exit\r',b'M5_CONSOLE_EXIT')])
        assert data.endswith(HTML.replace(b'Hello from HTML Kernel!',
                                          b'M5-D HTML WAS RECOMPILED!'))
        assert changed_iso.read_bytes()!=original.read_bytes()
        print('M5-D CHANGED HTML SOURCE -> NEW ISO + TRUE GUEST OUTPUT PASS')

        new_program=work/'modified-app.S'
        original_asm=(ROOT/'examples/user-programs/hello.S').read_text()
        assert original_asm.count('$2026')==1
        new_program.write_text(original_asm.replace('$2026','$2027'))
        new_iso=work/'changed-app.iso'
        build(source,new_iso,work,cache,'--user-app-source',str(new_program))
        data,_=execute(new_iso,[(b'run /apps/hello.hke\r',b'M5_D_RUN_END'),
                                (b'exit\r',b'M5_CONSOLE_EXIT')])
        assert data.count(b'M5_C_USER_VALUE=2027')==1
        assert b'M5_C_USER_VALUE=2026' not in data
        assert new_iso.read_bytes()!=original.read_bytes()
        print('M5-D ALTERED STANDALONE CPL3 IMAGE -> DIFFERENT LIVE USER OUTPUT PASS')

        image=work/'hello.hke'
        good=build_program(ROOT/'examples/user-programs/hello.S',image)
        damaged=work/'corrupt.hke'
        damaged.write_bytes(good[:40]+bytes((good[40]^1,))+good[41:])
        bad_iso=work/'damaged.iso'
        build(source,bad_iso,work,cache,'--user-app-image',str(damaged))
        data,_=execute(bad_iso,[(b'run /apps/hello.hke\r',b'M5_C_IMAGE_INVALID')],
                       expected_exit=53)
        assert b'M5_D_RUN_END' not in data and HTML not in data
        print('M5-D INTERACTIVE run -> INVALID CHECKSUM FAIL-CLOSED EXIT53 PASS')

        for flags in (('--romfs-shell','--romfs-probe'),
                      ('--romfs-shell','--user-preempt-probe'),
                      ('--romfs-shell','--romfs-negative'),
                      ('--user-app-source',str(new_program))):
            missing=work/'invalid.iso'
            cmd=[sys.executable,str(ROOT/'scripts/build_boot.py'),'--out',str(missing),*flags]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
            assert result.returncode!=0 and not missing.exists(),(flags,result.stderr)
        print('M5-D INCOMPATIBLE BUILD MODES DENIED BEFORE ISO')
    print('M5-D ACTUAL BOOT -> UART CAT -> RUN CPL3 -> INVALID INPUT -> EXIT ACCEPTANCE PASS')

if __name__=='__main__': main()
