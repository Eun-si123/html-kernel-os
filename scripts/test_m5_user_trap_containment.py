#!/usr/bin/env python3
"""M5-E3-B: actual CPL3 #DE, #DB, #BP survive; kernel and legacy modes stay fail-stop."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from build_user_image import build as build_user_image
from test_boot import ROOT
from test_m5_interactive_run import APP_TRACE, BASE, HTML, build as build_legacy, exercise
from test_m5_user_fault_recovery import build as build_recover
from test_m5_user_timeout import build as build_timer, CPU, TIMER

FAULT_NAMES=('de','db','bp')

def build_guest(work:Path,cache:Path,romfs:Path, *, timer:bool)->Path:
    iso=work/('trap-timer.iso' if timer else 'trap-recover.iso')
    source=ROOT/'examples/kernel.html'
    if timer:
        build_timer(source,iso,work,cache,'--romfs-root',str(romfs))
    else:
        build_recover(source,iso,work,cache,'--romfs-root',str(romfs))
    return iso


def prove_full_guest(iso:Path,*,timer:bool)->None:
    cpu=CPU if timer else None
    good=APP_TRACE.replace(b'M5_C_USER_PAGES_READY\n',
                           b'M5_C_USER_PAGES_READY\n'+TIMER) if timer else APP_TRACE
    commands=[(b'help\r',b'M5_HELP help ls cat /path run /path exit')]
    for path in ('/apps/fault-de.hke','/apps/fault-db.hke','/apps/fault-bp.hke',
                 '/end-bp.hke','/end-db.hke','/apps/fault-ud.hke'):
        commands.append((f'run {path}\r'.encode(),b'M5_ERR_USER_FAULT'))
        commands.append((b'run /apps/hello.hke\r',good))
    if timer:
        commands.extend(((b'run /apps/spin.hke\r',b'M5_ERR_USER_TIMEOUT'),
                         (b'run /apps/hello.hke\r',good)))
    commands.append((b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML))
    for boot in range(2):
        trace,uart=exercise(iso,commands,HTML,cpu=cpu)
        assert trace.startswith(BASE) and trace.endswith(b'M5_CONSOLE_EXIT\n'+HTML)
        assert trace.count(b'M5_E_USER_DE\n')==1,(boot,trace)
        assert trace.count(b'M5_E_USER_DB\n')==2,(boot,trace)
        assert trace.count(b'M5_E_USER_BP\n')==2,(boot,trace)
        assert trace.count(b'M5_E_USER_UD\n')==1,(boot,trace)
        assert trace.count(b'M5_ERR_USER_FAULT\n')==6,(boot,trace)
        assert trace.count(b'M5_E_FAULT_FRAMES_RECLAIMED\n')==6,(boot,trace)
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==(7 if timer else 6),(boot,trace)
        assert trace.count(b'M5_RUN_DONE\n')==(7 if timer else 6),(boot,trace)
        assert trace.count(good)==(7 if timer else 6),(boot,trace)
        assert uart.count(b'M5_ERR_USER_FAULT')==6,(boot,uart)
        assert uart.count(b'M5_C_USER_VALUE=2026')==(7 if timer else 6),(boot,uart)
        assert b'M3_EXCEPTION V=00' not in trace and b'M3_EXCEPTION V=01' not in trace
        assert b'M3_EXCEPTION V=0D' not in trace
        if timer:
            assert trace.count(TIMER)==14,(boot,trace)
            assert trace.count(b'M5_E2_REAL_USER_IRQ_LIMIT\n')==1,(boot,trace)
            assert trace.count(b'M5_E2_TIMEOUT_FRAMES_RECLAIMED\n')==1,(boot,trace)
            assert trace.count(b'M5_ERR_USER_TIMEOUT\n')==1,(boot,trace)
        print(f'M5-E3-B REAL QEMU {"x2APIC" if timer else "NO-TIMER"} BOOT {boot+1}/2: '
              '6 user CPU traps + 6 healthy reruns + clean exit PASS',flush=True)


def prove_legacy_fail_stop(work:Path,cache:Path)->None:
    for name,vector in (('de',b'00'),('db',b'01'),('bp',b'0D')):
        # Without --user-fault-recover even a *genuine* CPL3 trap must not
        # invoke a recovery path. INT3 gets #GP(0x1a) on DPL0 IDT in D1.
        iso=work/(name+'-legacy.iso')
        build_legacy(ROOT/'examples/kernel.html',iso,work,cache,
                     ['--user-app-source',str(ROOT/'examples/user-programs'/('fault-'+name+'.S'))])
        with tempfile.TemporaryDirectory(prefix='htmlk-e3b-fatal-') as tmp:
            debug=Path(tmp)/'debug.log'
            command=['qemu-system-x86_64','-M','q35','-m','256M',
                     '-cdrom',str(iso),'-boot','d','-display','none',
                     '-monitor','none','-net','none','-serial','stdio',
                     '-debugcon','file:'+str(debug),
                     '-global','isa-debugcon.iobase=0xe9',
                     '-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-no-reboot']
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            def current()->bytes:return debug.read_bytes() if debug.exists() else b''
            try:
                start=time.monotonic()
                while BASE not in current():
                    assert proc.poll() is None and time.monotonic()-start<17,(name,current())
                    time.sleep(.02)
                for ch in b'run /apps/hello.hke\r':
                    assert proc.stdin is not None
                    proc.stdin.write(bytes((ch,)));proc.stdin.flush();time.sleep(.008)
                _,stderr=proc.communicate(timeout=12)
                trace=current()
                assert proc.returncode==45,(name,proc.returncode,trace,stderr)
                assert b'M3_EXCEPTION V='+vector in trace,(name,trace)
                assert trace.count(b'M5_PROMPT> ')==1,(name,trace)
                assert b'M5_ERR_USER_FAULT' not in trace,(name,trace)
                assert b'M5_E_FAULT_FRAMES_RECLAIMED' not in trace,(name,trace)
                if name=='bp': assert b'M3_ERROR=0x000000000000001A' in trace,trace
            finally:
                if proc.poll() is None:
                    proc.kill();proc.communicate(timeout=4)
    print('M5-E3-B LEGACY IDT DPL0 / RING3 TRAP FATAL NEGATIVES (DE,DB,BP) PASS')


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-e3-traps-') as tmp:
        work=Path(tmp)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        romfs=work/'romfs'
        shutil.copytree(ROOT/'examples/romfs',romfs)
        # Trap-class RIP points to the first byte *after* the trap;
        # a single-byte program ensures the exact one-past-end guard is real.
        for mnemonic,opcode in (('bp',0xcc),('db',0xf1)):
            asm=work/(mnemonic+'-end.S')
            asm.write_text('.section .text\n.global htmlk_user_program_start\n'
                           'htmlk_user_program_start:\n'
                           f'    .byte 0x{opcode:02x}\n'
                           '.section .note.GNU-stack,"",@progbits\n')
            build_user_image(asm,romfs/(f'end-{mnemonic}.hke'))
        prove_full_guest(build_guest(work,cache,romfs,timer=False),timer=False)
        prove_full_guest(build_guest(work,cache,romfs,timer=True),timer=True)
        prove_legacy_fail_stop(work,cache)
    print('M5-E3-B CPU TRAP CONTAINMENT, REAL TIMER, BOUNDARY RIP, FAIL-STOP ACCEPTANCE PASS')

if __name__=='__main__':main()
