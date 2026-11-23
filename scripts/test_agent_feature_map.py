"""Positive/negative contract tests for the repository-owned cross-agent map."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_feature_map import MAP, git_diff, summarize, validate


class FeatureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = json.loads(MAP.read_text(encoding="utf-8"))

    def test_mapping_has_existing_sources_and_regressions(self):
        self.assertEqual({entry["id"] for entry in validate(self.real)},
                         {"html-grammar-codegen", "static-site", "m3-memory-bootstrap",
                          "m3-exception-idt", "m3-private-paging",
                          "m3-owned-fault-recovery"})

    def test_changed_m3_c_source_maps_native_regressions(self):
        report = summarize(validate(self.real), ["boot/page_pool.c"])
        self.assertEqual(report["affectedFeatures"][0]["feature"], "m3-memory-bootstrap")
        self.assertIn("tests/test_m3_memory.py", report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_new_exception_idt_source_maps_real_cpu_fault_evidence(self):
        report = summarize(validate(self.real), ["boot/exception_idt.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-exception-idt"])
        self.assertIn("tests/test_exception_idt.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_exception_idt.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_changed_private_paging_source_maps_real_cr3_and_pf_proof(self):
        report = summarize(validate(self.real), ["boot/paging_probe.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-private-paging"])
        self.assertIn("tests/test_paging_tables.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_paging_probe.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_owner_registry_maps_to_genuine_qemu_fault_recovery(self):
        report = summarize(validate(self.real), ["boot/frame_owner.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-owned-fault-recovery"])
        self.assertIn("tests/test_frame_owner.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_paging_recovery.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_changed_compiler_reports_tests_but_not_pass(self):
        changes = summarize(validate(self.real), ["compiler/htmlk.py"])
        feature = changes["affectedFeatures"][0]
        self.assertEqual(feature["feature"], "html-grammar-codegen")
        self.assertEqual(feature["automatedEvidence"], "not-run")
        self.assertEqual(feature["fieldStatus"], "not-run")
        self.assertEqual(feature["review"], "review-existing-regressions-for-new-behavior")

    def test_changed_regression_is_not_evidence_of_pass(self):
        changes = summarize(validate(self.real),
                            ["compiler/htmlk.py", "tests/test_compiler.py"])
        self.assertEqual(changes["affectedFeatures"][0]["review"],
                         "regression-test-change-present")
        self.assertEqual(changes["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_unmapped_source_never_disappears(self):
        report = summarize(validate(self.real), ["compiler/new_backend.py"])
        self.assertEqual(report["unmappedSourceFiles"], ["compiler/new_backend.py"])

    def test_bad_schema_and_duplicate_ids(self):
        changed = copy.deepcopy(self.real)
        changed["schemaVersion"] = 5
        with self.assertRaisesRegex(ValueError, "schemaVersion"):
            validate(changed)
        changed = copy.deepcopy(self.real)
        changed["features"].append(copy.deepcopy(changed["features"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate/invalid"):
            validate(changed)

    def test_missing_file_or_path_escape_rejected(self):
        for bad in ("../secret", "/etc/hosts", "tests/does_not_exist.py"):
            changed = copy.deepcopy(self.real)
            changed["features"][0]["regressions"] = [bad]
            with self.assertRaises(ValueError):
                validate(changed)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "compiler").mkdir()
            (root / "tests").mkdir()
            (root / "docs").mkdir()
            (root / "compiler" / "outside.py").symlink_to("/etc/hosts")
            (root / "tests" / "test_x.py").write_text("pass\n")
            (root / "docs" / "VALIDATION.md").write_text("evidence\n")
            doc = {"schemaVersion": 1, "features": [{
                "id": "bad-path",
                "source": ["compiler/outside.py"],
                "regressions": ["tests/test_x.py"],
                "fieldEvidence": ["docs/VALIDATION.md"],
            }]}
            with self.assertRaisesRegex(ValueError, "out-of-root"):
                validate(doc, root)

    def test_injection_in_git_ref_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid Git reference"):
            git_diff("--exec=bad", "HEAD")
        with self.assertRaisesRegex(ValueError, "invalid Git reference"):
            git_diff("main..evil", "HEAD")


if __name__ == "__main__":
    unittest.main()
