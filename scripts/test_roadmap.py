"""Positive and negative checks for machine-readable Markdown milestones."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roadmap import ROADMAP, parse_roadmap

GOOD = """# Roadmap

| ID | Goal | Depends on | Acceptance gate |
| -- | -- | -- | -- |
| **M0** | Prototype | — | Compile a real x86-64 object file with tests |
| **M1 — NEXT** | Boot | M0 | Run a reproducible QEMU boot with exact output |
| **M2** | Variables | M0; M1 | Compile conditional programs and demonstrate native execution |
"""


class RoadmapContractTests(unittest.TestCase):
    def test_real_repository_roadmap(self):
        report = parse_roadmap(ROADMAP.read_text(encoding="utf-8"))
        # M3 bounded real QEMU memory/fault gate is now evidenced; M4 is next.
        self.assertEqual(report["nextSuggested"], "M4")
        self.assertEqual([m["id"] for m in report["milestones"]],
                         [f"M{i}" for i in range(7)])
        self.assertIn("M1", report["milestones"][2]["dependsOn"])
        self.assertIn("not measured progress", report["limitation"])

    def test_example_is_parseable(self):
        report = parse_roadmap(GOOD)
        self.assertEqual(len(report["milestones"]), 3)
        self.assertEqual(report["milestones"][2]["dependsOn"], ["M0", "M1"])

    def test_missing_next_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one NEXT"):
            parse_roadmap(GOOD.replace(" — NEXT", ""))

    def test_multiple_next_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one NEXT"):
            parse_roadmap(GOOD.replace("**M2**", "**M2 — NEXT**"))

    def test_duplicate_milestone_rejected(self):
        with self.assertRaisesRegex(ValueError, "sequential"):
            parse_roadmap(GOOD.replace("**M2**", "**M1**"))

    def test_unknown_or_future_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown or forward"):
            parse_roadmap(GOOD.replace("**M1 — NEXT** | Boot | M0",
                                       "**M1 — NEXT** | Boot | M3"))

    def test_missing_acceptance_rejected(self):
        with self.assertRaisesRegex(ValueError, "acceptance"):
            parse_roadmap(GOOD.replace(
                "Run a reproducible QEMU boot with exact output", "PASS"))


if __name__ == "__main__":
    unittest.main()
