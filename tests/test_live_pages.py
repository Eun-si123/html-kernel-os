"""Static contract for a separate genuine native HTML user guest on Pages.

This test never claims to have booted a web browser. Real CPU guest proof is
scripts/test_live_site.py; frontend browser proof is a distinct test class.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site/live'

class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
    def handle_starttag(self, tag, attrs):
        found = dict(attrs).get('id')
        if found: self.ids.append(found)

class LivePagesTests(unittest.TestCase):
    def test_separate_page_and_real_uart_controls(self):
        html = (SITE/'index.html').read_text()
        js = (SITE/'live.js').read_text()
        css = (SITE/'live.css').read_text()
        parser = Ids()
        parser.feed(html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for name in ('journal-output','journal-title','journal-position','journal-speed',
                     'journal-play','journal-pause','journal-step','journal-status',
                     'html-editor','editor-title','editor-bytes','editor-status',
                     'editor-command','editor-copy','editor-save','editor-reset',
                     'start','stop','fullscreen','terminal','source','source-hash',
                     'iso-hash','boot-event','romfs-match','screen_container','local-iso','local-html','command',
                     'command-form','send','message','state'):
            self.assertIn(name, parser.ids)
        for token in ("import V86 from '../vendor/libv86.mjs'",
                      'serial0-output-byte', 'serial0_send',
                      "cpu_type:'x86_64'", 'cdrom:{buffer:data}',
                      'crypto.subtle.digest', 'M5_PROMPT> ',
                      'M5_RUN_EXIT_CODE=', 'M5_C_USER_FRAMES_RECLAIMED',
                      'SOURCE_BEGIN', 'SOURCE_END', 'expectedSourceBytes'):
            self.assertIn(token, js)
        self.assertNotIn('innerHTML', js)
        self.assertNotIn('M5_C_USER_VALUE=4294967296', js,
                         'never insert hardcoded demo output in a live UART log')
        journal = (SITE/'journal.mjs').read_text()
        for token in ('createBootJournal', 'BootTrace', 'vgaCell(cell)',
                      'uartByte(byte)', 'captureFrame()', 'JOURNAL_LIMIT = 240',
                      'SeaBIOS', 'formatted(', 'textContent'):
            self.assertIn(token, journal)
        self.assertNotIn('innerHTML', journal)
        self.assertIn("import {createBootJournal} from './journal.mjs'", js)
        self.assertIn('autostart:false', js)
        self.assertIn('machine.run().catch', js)
        self.assertIn('bootJournal.vgaCell(cell)', js)
        self.assertIn('bootJournal.uartByte(byte)', js)
        self.assertIn('.vga canvas{width:100%;max-width:100%', css)
        self.assertIn('(prefers-color-scheme:dark)', css)
        self.assertIn('max-width:520px', css)
        self.assertIn('data-command="cat /source.html"', html)
        editor = (SITE/'editor.mjs').read_text()
        self.assertIn('<script type="module" src="./editor.mjs"></script>', html)
        self.assertIn('브라우저에서 HTML형 언어 코드를 작성', html)
        for marker in ('SOURCE_LIMIT = 4096','sourceBytes','sourceState','TextEncoder',
                       'EXPORT_FILENAME','URL.createObjectURL','anchor.download',
                       'BUILD_COMMAND','M2-UX4', 'setupEditor'):
            self.assertIn(marker, editor)
        self.assertNotIn('fetch(', editor)
        self.assertNotIn('eval(', editor)
        self.assertNotIn('innerHTML', editor)
        self.assertIn('max-width:780px', css)
        self.assertIn('브라우저 메모리에서만 실행', html)
        self.assertIn('html-kernel-live.iso', html)
        self.assertIn('--source 내프로그램.html', html)
        for token in ('localIsoFile','localHtmlFile','arrayBuffer()',
                      'MAX_LOCAL_ISO_BYTES','CD001','TextDecoder',
                      'localIsoInput.disabled', 'chooseLocalHtml',
                      'chooseLocalIso', 'sourceVerified'):
            self.assertIn(token, js)
        self.assertIn('읽기 전용', html)
        self.assertIn('정적 사이트', html)
        self.assertIn('x2APIC 타임아웃 없이', html)
    def test_pages_exact_iso_source_manifest_build_and_native_test(self):
        pages = (ROOT/'.github/workflows/pages.yml').read_text()
        ci = (ROOT/'.github/workflows/ci.yml').read_text()
        builder = (ROOT/'scripts/build_live_site.py').read_text()
        for token in ('scripts/build_live_site.py', 'scripts/test_live_site.py',
                      'html-kernel-live.iso', 'html-kernel-live.json',
                      'live/index.html', 'live/live.js',
                      'examples/user-programs/html-u64-report.html'):
            self.assertIn(token, pages)
        self.assertIn('scripts/test_live_site.py', ci)
        self.assertIn('scripts/test_live_source_mutation.py', ci)
        self.assertIn('scripts/test_live_source_mutation.py', pages)
        self.assertIn('--user-app-html', builder)
        self.assertIn('--romfs-run-console', builder)
        self.assertIn('--user-fault-recover', builder)
        self.assertNotIn('"--user-timeout"', builder)
        self.assertIn('source.html', builder)
        self.assertIn('shutil.copytree', builder)
        self.assertIn('scripts/test_live_editor_native.py', ci)
        self.assertIn('scripts/test_live_editor_native.py', pages)
        self.assertIn('node --test scripts/test_live_editor.mjs', ci)
        self.assertIn('node --test scripts/test_live_editor.mjs', pages)
        self.assertIn('test -s public/live/editor.mjs', pages)
        self.assertIn('node --test scripts/test_live_boot_journal.mjs', ci)
        self.assertIn('node --test scripts/test_live_boot_journal.mjs', pages)
        self.assertIn('test -s public/live/journal.mjs', pages)
        self.assertIn('scripts/test_local_live_iso.py', ci)
        self.assertIn('scripts/test_local_live_iso.py', pages)
        self.assertIn('--source', builder)
        self.assertIn('test_exit', builder)
        self.assertTrue((ROOT/'examples/user-programs/html-u64-report.html').is_file())
        self.assertIn('href="./live/"', (ROOT/'site/index.html').read_text())

if __name__ == '__main__':
    unittest.main()
