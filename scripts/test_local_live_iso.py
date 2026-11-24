#!/usr/bin/env python3
"""Build USER-EDITED HTML with existing native compiler; real QEMU acceptance.

No fake browser compilation: this test verifies CLI --source, immutable
ROMFS source snapshot, distinct HKEX instructions and actual CPU result.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT
from test_m5_interactive_run import exercise, HTML

SOURCE = ROOT/'examples/user-programs/html-u64-report.html'
OLD_NUMBER='18446744073709551615'
NEW_NUMBER='12345678901234567890'

def hash_file(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main()->None:
    original=SOURCE.read_text(encoding='utf-8')
    assert original.count(OLD_NUMBER)==1
    assert '<halt code="7"/>' in original
    with tempfile.TemporaryDirectory(prefix='htmlk-browser-local-html-') as t:
        work=Path(t)
        edited=work/'my-edited.html'
        edited.write_text(original.replace(OLD_NUMBER,NEW_NUMBER)
                          .replace('<halt code="7"/>','<halt code="9"/>'),
                          encoding='utf-8')
        dest=work/'local-image'
        completed=subprocess.run([
            sys.executable,str(ROOT/'scripts/build_live_site.py'),
            '--source',str(edited),'--out-dir',str(dest)],cwd=ROOT,
            capture_output=True,text=True,check=False,timeout=80)
        assert completed.returncode==0,(completed.stdout[-2200:],completed.stderr[-1000:])
        iso=dest/'html-kernel-live.iso'
        manifest=json.loads((dest/'html-kernel-live.json').read_text())
        assert manifest['image_sha256']==hash_file(iso)
        assert manifest['image_bytes']==iso.stat().st_size
        assert manifest['user_source']=='local/my-edited.html'
        assert 'expected_marker' not in manifest, 'custom source cannot inherit default exit7'
        assert manifest['embedded_source_sha256']==hash_file(edited)
        assert manifest['embedded_source_bytes']==len(edited.read_bytes())
        assert iso.read_bytes()[32769:32774]==b'CD001'
        commands=[
            (b'cat /source.html\r',b'M5_CAT_END\n'),
            (b'run /apps/hello.hke\r',b'M5_RUN_EXIT_CODE=9\n'),
            (b'run /apps/hello.hke\r',b'M5_RUN_EXIT_CODE=9\n'),
            (b'exit\r',b'M5_CONSOLE_EXIT\n'+HTML)]
        trace,uart=exercise(iso,commands,HTML)
        exact=b'M5_CAT_BEGIN /source.html\n'+edited.read_bytes()+b'M5_CAT_END\n'
        assert trace.count(exact)==uart.count(exact)==1
        new=('M5_C_USER_VALUE='+NEW_NUMBER+'\n').encode()
        old=('M5_C_USER_VALUE='+OLD_NUMBER+'\n').encode()
        assert trace.count(new)==uart.count(new)==2
        assert old not in trace and old not in uart
        assert trace.count(b'M5_RUN_EXIT_CODE=9\n')==2
        assert trace.count(b'M5_C_USER_FRAMES_RECLAIMED\n')==2
        print('M5 WEB LOCAL HTML --source CLI → distinct native ISO/HKEX → '
              'real QEMU two runs, changed u64+exit9, raw ROMFS equality PASS')
        # Security regression: only explicitly bounded read-only user source;
        # no silent truncation/oversized kernel ROMFS file.
        oversize=work/'too-large.html'
        oversize.write_bytes(edited.read_bytes()+b'\n'*(4097-len(edited.read_bytes())))
        rejected=subprocess.run([
            sys.executable,str(ROOT/'scripts/build_live_site.py'),
            '--source',str(oversize),'--out-dir',str(work/'oversize-iso')],
            cwd=ROOT,capture_output=True,text=True,check=False,timeout=20)
        assert rejected.returncode!=0
        assert '4096 bytes' in rejected.stderr
        print('M5 WEB LOCAL oversized source >4KiB rejected before ISO PASS')

if __name__=='__main__':
    main()
