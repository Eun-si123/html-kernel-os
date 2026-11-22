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
        self.assertIn("./styles.css", self.parser.stylesheets)
        for asset in self.parser.scripts + self.parser.stylesheets:
            self.assertTrue((SITE / asset).is_file(), asset)

    def test_external_links_protect_reverse_tab(self):
        for href, target, rel in self.parser.anchors:
            if target == "_blank":
                self.assertTrue(href.startswith("https://"))
                self.assertIn("noopener", rel.split())
                self.assertIn("noreferrer", rel.split())

    def test_the_site_does_not_claim_boot_completed(self):
        self.assertIn("커널 부팅 미구현", self.html)
        self.assertIn("READ-ONLY PREVIEW", self.html)
        self.assertIn("GitHub", self.html)
        self.assertRegex(self.html, r'<html lang="ko">')

    def test_copy_button_and_tabs_have_handlers(self):
        js = (SITE / "app.js").read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", js)
        self.assertIn("aria-selected", js)
        self.assertIn("keydown", js)


if __name__ == "__main__":
    unittest.main()
