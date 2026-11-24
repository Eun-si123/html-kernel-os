"""Prevent published M2-UX and Web-D release gates from reverting to 'pending'.

This documents the PRs and public Chromium/native evidence verified at the
2026-11-24 release checkpoint; it is not a live GitHub Pages uptime check.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = {
    'M2-UX3': ('#107', False),
    'M2-UX4': ('#108', True),
    'M2-UX5': ('#109', False),
    'M2-UX6': ('#111', True),
    'M5 Web-D': ('#110', True),
}


class M2ReleaseStatusTests(unittest.TestCase):
    def test_canonical_roadmap_and_status_headings_match_actual_merges(self):
        roadmap = (ROOT/'docs/ROADMAP.md').read_text()
        status = (ROOT/'docs/STATUS.md').read_text()
        for milestone, (pr, _) in RELEASES.items():
            with self.subTest(milestone=milestone):
                section = next((x for x in roadmap.splitlines()
                                if x.startswith('**'+milestone)), None)
                self.assertIsNotNone(section)
                self.assertIn('merged PR '+pr, section)
                self.assertNotIn('merge pending', section)
                heading = next((x for x in status.splitlines()
                                if x.startswith('## '+milestone)), None)
                self.assertIsNotNone(heading)
                self.assertIn('PR '+pr, heading)
                self.assertIn('merged', heading)
                self.assertNotIn('pending', heading)
        self.assertIn('NEXT=M5', __import__('subprocess').run([
            'python3', str(ROOT/'scripts/roadmap.py'), '--check'],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout)

    def test_public_release_docs_do_not_claim_unverified_current_features(self):
        readme=(ROOT/'README.md').read_text()
        refs={
            'docs/M2_WEB_EDITOR.md': '#108',
            'docs/M2_LANGUAGE_LSP.md': '#109',
            'docs/M2_PUBLIC_LANGUAGE_GRAMMAR.md': '#111',
            'docs/M5_WEB_BOOT_JOURNAL.md': '#110',
        }
        for path, pr in refs.items():
            with self.subTest(path=path):
                text=(ROOT/path).read_text()
                self.assertIn(pr, text)
                self.assertRegex(text.lower(), r'pass|passed')
                self.assertNotIn('exact PR-head CI, merge and public Pages deployment remain separate evidence gates', text)
        self.assertIn('GitHub Pages does **not** compile a new native ISO', readme)
        self.assertIn('physical', (ROOT/'docs/STATUS.md').read_text().lower())

    def test_future_ux_proposals_do_not_reuse_already_delivered_phase_ids(self):
        source = (ROOT/'docs/LANGUAGE_HUMAN_AGENT.md').read_text()
        self.assertIn('Future M2 language usability work — proposed, NOT shipped',source)
        self.assertIn('Issue #112', source)
        for old in ('**M2-UX2:** editor integration',
                    '**M2-UX3:** tagged standard library',
                    '**M2-UX4:** measured beginner'):
            self.assertNotIn(old, source)


if __name__ == '__main__':
    unittest.main()
