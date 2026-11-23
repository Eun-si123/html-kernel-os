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
        for name in ('start','stop','fullscreen','terminal','source','source-hash',
                     'iso-hash','boot-event','screen_container','command',
                     'command-form','send','message','state'):
            self.assertIn(name, parser.ids)
        for token in ("import V86 from '../vendor/libv86.mjs'",
                      'serial0-output-byte', 'serial0_send',
                      "cpu_type:'x86_64'", 'cdrom:{buffer:data}',
                      'crypto.subtle.digest', 'M5_PROMPT> ',
                      'M5_RUN_EXIT_CODE=7', 'M5_C_USER_FRAMES_RECLAIMED'):
            self.assertIn(token, js)
        self.assertNotIn('innerHTML', js)
        self.assertNotIn('M5_C_USER_VALUE=4294967296', js,
                         'never insert hardcoded demo output in a live UART log')
        self.assertIn('(prefers-color-scheme:dark)', css)
        self.assertIn('max-width:520px', css)
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
        self.assertIn('--user-app-html', builder)
        self.assertIn('--romfs-run-console', builder)
        self.assertIn('--user-fault-recover', builder)
        self.assertNotIn('"--user-timeout"', builder)
        self.assertIn('test_exit', builder)
        self.assertTrue((ROOT/'examples/user-programs/html-u64-report.html').is_file())
        self.assertIn('href="./live/"', (ROOT/'site/index.html').read_text())

if __name__ == '__main__':
    unittest.main()
