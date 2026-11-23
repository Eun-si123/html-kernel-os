"""Static website smoke tests. These are NOT browser or kernel execution tests."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.anchors = []
        self.scripts = []
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if "aria-controls" in a:
            self.references.append(a["aria-controls"])
        if tag == "a" and "href" in a:
            self.anchors.append((a["href"], a.get("target"), a.get("rel", "")))
        if tag == "script" and "src" in a:
            self.scripts.append(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet":
            self.stylesheets.append(a.get("href"))


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (SITE / "index.html").read_text(encoding="utf-8")
        cls.parser = PageParser()
        cls.parser.feed(cls.html)

    def test_referenced_panels_and_navigation_targets_exist(self):
        self.assertEqual(len(self.parser.ids), len(set(self.parser.ids)))
        ids = set(self.parser.ids)
        for ref in self.parser.references:
            self.assertIn(ref, ids)
        for href, _, _ in self.parser.anchors:
            if href.startswith("#"):
                self.assertIn(href[1:], ids, f"missing section: {href}")

    def test_assets_exist_and_js_syntax_can_be_checked(self):
        self.assertIn("./app.js", self.parser.scripts)
        self.assertIn("./styles.css?v=20261123-auto-theme2", self.parser.stylesheets)
        for asset in self.parser.scripts + self.parser.stylesheets:
            asset_path = asset.split("?", 1)[0]
            self.assertTrue((SITE / asset_path).is_file(), asset)

    def test_external_links_protect_reverse_tab(self):
        for href, target, rel in self.parser.anchors:
            if target == "_blank":
                self.assertTrue(href.startswith("https://"))
                self.assertIn("noopener", rel.split())
                self.assertIn("noreferrer", rel.split())

    def test_the_site_reports_tested_boot_and_limits(self):
        self.assertIn("QEMU 로컬 검증 성공", self.html)
        self.assertIn("READ-ONLY PREVIEW", self.html)
        self.assertIn("./play.html", self.html)
        self.assertIn("아직 미구현/미검증", self.html)
        self.assertRegex(self.html, r'<html lang="ko">')

    def test_browser_laboratory_has_static_assets_and_truthful_status(self):
        html = (SITE / "play.html").read_text(encoding="utf-8")
        script = (SITE / "play.js").read_text(encoding="utf-8")
        self.assertTrue((SITE / "play.css").is_file())
        self.assertTrue((SITE / "vendor/libv86.mjs").is_file())
        self.assertTrue((SITE / "vendor/v86.wasm").is_file())
        self.assertTrue((SITE / "vendor/v86-bochs-vga.js").is_file())
        self.assertIn('id="boot-output"', html)
        self.assertIn('id="boot-start"', html)
        self.assertIn("serial0-output-byte", script)
        self.assertIn('value="video" selected', html)
        self.assertIn("html-kernel-video.iso", script)
        self.assertIn('id="boot-replay"', html)
        self.assertIn('id="replay-speed"', html)
        self.assertIn('id="display-fullscreen"', html)
        self.assertIn("serialVerified", script)
        self.assertIn("playRecordedSerial", script)
        self.assertIn("requestFullscreen()", script)
        self.assertIn("가상 CPU 부팅 속도를 조작하는 기능은 아니야", script)
        self.assertIn("실제 VGA", html)
        pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("html-kernel-video.iso public/html-kernel-video.iso", pages)
        for filename in ("kernel.html", "framebuffer-kernel.html",
                         "math-kernel.html", "functions-kernel.html",
                         "scoped-functions-kernel.html", "else-kernel.html",
                         "u32-kernel.html", "signed-bits-kernel.html"):
            self.assertIn(f"examples/{filename} public/examples/{filename}", pages)
            self.assertIn(f"source: '{filename}'", script)
            self.assertTrue((ROOT / "examples" / filename).is_file())
        for control in ("vm-pace", "vm-pause", "boot-latest", "boot-events",
                        "boot-source", "boot-source-note", "boot-source-path",
                        "live-tag"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn("screen-put-char", script)
        self.assertIn("recordVgaCell", script)
        self.assertIn("latestEvent.textContent = kind", script)
        self.assertIn("실제 가상 CPU 실행 재개", script)
        self.assertIn("sourceLineForLiteral", script)
        self.assertIn("output.textContent = serial", script)
        self.assertIn("machine.run()", script)
        self.assertIn("machine.stop()", script)
        self.assertIn("관찰 모드", script)
        self.assertIn("ISO 자체는 전부 HTML이 아니고", html)
        self.assertIn("python scripts/test_video_screen.py", pages)
        self.assertIn("html-kernel.iso", script)
        self.assertIn("html-kernel-math.iso", script)
        self.assertIn("html-kernel-functions.iso", script)
        self.assertIn("html-kernel-scoped.iso", script)
        self.assertIn("html-kernel-else.iso", script)
        self.assertIn("html-kernel-u32.iso", script)
        self.assertIn("html-kernel-signed.iso", script)
        self.assertIn('value="signed"', html)
        self.assertIn('value="u32"', html)
        self.assertIn('value="branches"', html)
        self.assertIn('value="scoped"', html)
        self.assertIn('value="functions"', html)
        self.assertIn('id="kernel-demo"', html)
        self.assertIn("condition PASS", script)
        self.assertIn("./vendor/v86.wasm", script)
        self.assertIn("아직 구현되지 않았어", html)

    def test_editorial_layout_preserves_functionality_and_accessibility(self):
        home = (SITE / "index.html").read_text(encoding="utf-8")
        lab = (SITE / "play.html").read_text(encoding="utf-8")
        css = (SITE / "styles.css").read_text(encoding="utf-8")
        lab_css = (SITE / "play.css").read_text(encoding="utf-8")
        for text in ('class="skip-link"', 'id="main"'):
            self.assertIn(text, home)
            self.assertIn(text, lab)
        for text in ('id="tab-html"', 'id="tab-c"', 'id="copy-code"'):
            self.assertIn(text, home)
        for text in ('aria-current="page"', 'id="boot-stop"',
                     'id="iso-download"', 'aria-live="polite"',
                     'id="screen_container"'):
            self.assertIn(text, lab)
        for key in ("basic", "math", "functions", "scoped",
                    "branches", "u32", "signed"):
            self.assertIn(f'value="{key}"', lab)
        for text in ("--paper:", "--ink:", "focus-visible", "prefers-reduced-motion:reduce"):
            self.assertIn(text, css)
        self.assertIn('href="./styles.css?v=20261123-auto-theme2"', home)
        self.assertIn('href="./styles.css?v=20261123-auto-theme2"', lab)
        self.assertIn('href="./play.css?v=20261123-live-source6"', lab)
        self.assertIn("@media(max-width:480px)", lab_css)
        self.assertIn("aspect-ratio: 4/3", lab_css)
        self.assertIn("object-fit: contain", lab_css)
        self.assertIn("grid-template-columns: minmax(0,1fr)", lab_css)
        self.assertIn(".trace-grid", lab_css)
        self.assertIn(".boot-events", lab_css)
        self.assertIn(".source-view", lab_css)
        self.assertNotIn("@import", css)
        self.assertNotIn("linear-gradient(", css)
        self.assertNotIn("radial-gradient(", css)

    def test_os_color_scheme_on_home_and_boot_lab(self):
        home = (SITE / "index.html").read_text(encoding="utf-8")
        lab = (SITE / "play.html").read_text(encoding="utf-8")
        css = (SITE / "styles.css").read_text(encoding="utf-8")
        for page in (home, lab):
            self.assertIn('media="(prefers-color-scheme: light)"', page)
            self.assertIn('media="(prefers-color-scheme: dark)"', page)
        self.assertIn('color-scheme: light;', css)
        self.assertIn('@media (prefers-color-scheme: dark)', css)
        self.assertIn('color-scheme: dark;', css)
        self.assertIn('--paper: #151a17;', css)
        self.assertIn('.lab-status-bar', css)
        boot_css = (SITE / "play.css").read_text(encoding="utf-8")
        self.assertIn('@media (prefers-color-scheme: dark)', boot_css)
        self.assertIn('.lab-status-bar { background:#222b25;', boot_css)
        self.assertIn('play.css?v=20261123-live-source6', lab)

    def test_copy_button_and_tabs_have_handlers(self):
        js = (SITE / "app.js").read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", js)
        self.assertIn("aria-selected", js)
        self.assertIn("keydown", js)


if __name__ == "__main__":
    unittest.main()
