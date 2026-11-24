#!/usr/bin/env python3
"""Real x86-64 TinyCC HTML user image + EXACT rebuilt provenance + QEMU.

This opt-in backend does not change the canonical GCC HTML proof or claim
browser executable compilation. Set HTMLK_TEST_TCC for extracted local tcc.
"""
from __future__ import annotations
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from test_boot import ROOT
from test_m5_interactive_run import exercise,HTML
from build_tcc_html_user_image import build as build_tcc

TCC=os.environ.get('HTMLK_TEST_TCC','tcc')
MODES={
 'message':(
    ROOT/'examples/user-programs/html-message.html',
    ((b'M5_F2_USER_TEXT=Hello from HTML user mode!\n',1),),
    b'M5_RUN_DONE\n'),
 'multiple':(
    ROOT/'examples/user-programs/html-multireport.html',
    ((b'M5_F2_USER_TEXT=tick\n',2),(b'M5_C_USER_VALUE=2026\n',1)),
    b'M5_RUN_DONE\n'),
 'u64':(
    ROOT/'examples/user-programs/html-u64-report.html',
    ((b'M5_C_USER_VALUE=4294967296\n',2),
     (b'M5_C_USER_VALUE=18446744073709551615\n',1)),
    b'M5_RUN_EXIT_CODE=7\n'),
 'functions':(
    ROOT/'examples/human-agent-program.html',
    ((b'M5_C_USER_VALUE=6\n',3),(b'M5_C_USER_VALUE=4294967296\n',1)),
    b'M5_RUN_DONE\n'),
}


def compile_real_iso(source:Path,image:Path,iso:Path,work:Path,cache:Path,
                     *, tcc_proof:bool=True,timeout:bool=True)->subprocess.CompletedProcess:
    argv=[sys.executable,str(ROOT/'scripts/build_boot.py'),
          '--source',str(ROOT/'examples/kernel.html'),
          '--out',str(iso),'--work-dir',str(work),'--cache-dir',str(cache),
          '--exception-idt','--tss-ist','--romfs-run-console','--user-fault-recover',
          '--user-app-image',str(image),'--user-app-html-proof',str(source),
          '--test-exit']
    if timeout:argv.append('--user-timeout')
    if tcc_proof:argv.extend(('--user-app-tcc-proof','--user-app-tcc-path',TCC))
    return subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=145)


def run_source(name:str,source:Path,expected:tuple[tuple[bytes,int],...],
               exit_marker:bytes,temporary:Path,cache:Path)->bytes:
    image=temporary/(name+'.hke')
    new=build_tcc(source,image,tcc=TCC)
    assert new==image.read_bytes() and 33<=len(new)<=4096
    twin=temporary/(name+'.copy.hke')
    assert build_tcc(source,twin,tcc=TCC)==new,'non-deterministic TinyCC image for exact same source/toolchain'
    iso=temporary/(name+'.iso')
    done=compile_real_iso(source,image,iso,temporary/'build-work',cache)
    assert done.returncode==0,(name,done.stdout[-1400:],done.stderr[-1800:])
    assert 'ROMFS_CONTENT_SHA256=' in done.stdout
    trace,uart=exercise(iso,[(b'run /apps/hello.hke\r',b'M5_PROMPT> '),
                              (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)],HTML,
                        cpu='qemu64,+x2apic')
    assert b'M5_E2_X2APIC_TIMER_READY\n' in trace,(name,trace)
    for marker,amount in expected:
        assert trace.count(marker)==uart.count(marker)==amount,(name,marker,trace,uart)
    assert trace.count(exit_marker)==uart.count(exit_marker)==1,(name,exit_marker,trace)
    for marker in (b'M5_C_RING3_EXIT_OK\n',b'M5_C_USER_FRAMES_RECLAIMED\n'):
        assert trace.count(marker)==uart.count(marker)==1,(name,marker,trace)
    assert b'M5_ERR_USER_SYSCALL' not in trace
    assert b'M5_ERR_USER_FAULT' not in trace
    assert b'M5_ERR_USER_TIMEOUT' not in trace
    print('TCC_PROVED_QEMU_PASS',name,'HKEX_SHA256='+sha256(new).hexdigest(),
          'IMAGE_BYTES='+str(len(new)),flush=True)
    return new


def main()->None:
    with tempfile.TemporaryDirectory(prefix='htmlk-tcc-proof-e2e-') as td:
        folder=Path(td)
        cache=Path(os.environ.get('HTMLK_CACHE_DIR',str(ROOT/'build/.cache')))
        binary={}
        for name,(source,expected,exit_marker) in MODES.items():
            binary[name]=run_source(name,source,expected,exit_marker,folder,cache)
        source=folder/'mutation-2031.html'
        previous=(ROOT/'site/live/editor.mjs').read_text()
        assert 'value="2026"' in previous
        from subprocess import check_output
        template=check_output(['node','--input-type=module','-e',
            'import {TEMPLATE} from "./site/live/editor.mjs"; process.stdout.write(TEMPLATE)'],
            cwd=ROOT,timeout=8).decode()
        source.write_text(template.replace('value="2026"','value="2031"'))
        assert 'value="2031"' in source.read_text()
        native=run_source('changed',source,((b'M5_C_USER_VALUE=2031\n',1),),
                          b'M5_RUN_DONE\n',folder,cache)
        original=folder/'mutation-2026.html'
        original.write_text(template)
        image=build_tcc(original,folder/'original.hke',tcc=TCC)
        assert image!=native
        print('TCC_SOURCE_MUTATION_CHANGED_ACTUAL_NATIVE_IMAGE_AND_RING3_OUTPUT_PASS',flush=True)
        # Negative: a precompiled TCC image must NOT claim GCC proof. The two
        # backends differ even for the same typed source, by design.
        wrong=compile_real_iso(source,folder/'original.hke',folder/'rejected.iso',
                               folder/'build-work',cache)
        assert (wrong.returncode!=0 and
                'does not match precompiled HKEX bytes' in wrong.stderr), (wrong.stdout[-700:],wrong.stderr[-700:])
        assert not (folder/'rejected.iso').exists()
        gcc_not_tcc=compile_real_iso(original,folder/'original.hke',folder/'gcc-rejected.iso',
                                    folder/'build-work',cache,tcc_proof=False)
        assert gcc_not_tcc.returncode!=0 and 'does not match precompiled HKEX bytes' in gcc_not_tcc.stderr
        no_timeout=compile_real_iso(original,folder/'original.hke',folder/'no-timeout.iso',
                                    folder/'build-work',cache,timeout=False)
        assert no_timeout.returncode!=0 and 'requires guarded interactive x2APIC timeout mode' in no_timeout.stderr
        print('TCC_NEGATIVE_WRONG_SOURCE_GCC_IMPERSONATION_AND_MISSING_TIMER_REJECTED_PASS',flush=True)


if __name__=='__main__':main()
