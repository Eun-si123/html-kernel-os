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
                          "m3-owned-fault-recovery", "m3-tss-ist",
                          "m3-bounded-multipage", "m4-cooperative-kernel-tasks",
                          "m4-pit-irq-pacing", "m4-x2apic-preemption",
                          "m4-ring3-user-syscall",
                          "m4-ring3-fault-containment",
                          "m4-ring3-preemptive-survival",
                          "m5-romfs-readonly", "m5-serial-console",
                          "m5-romfs-user-executable", "m5-interactive-romfs-run",
                          "m5-guarded-user-fault-recovery", "m5-x2apic-user-timeout",
                          "m5-html-language-user-program", "m5-checked-user-text-syscall",
                          "m5-bounded-html-user-multi-report"})

    def test_changed_m4_scheduler_maps_native_qemu_and_state_oracles(self):
        report = summarize(validate(self.real), ["boot/task_switch.S"])
        self.assertEqual([item["feature"] for item in report["affectedFeatures"]],
                         ["m4-cooperative-kernel-tasks"])
        self.assertIn("tests/test_m4_task_model.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_m4_tasks.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_x2apic_assembly_maps_frame_layout_and_real_irq_proof(self):
        report = summarize(validate(self.real), ["boot/preempt_switch.S"])
        self.assertEqual([item["feature"] for item in report["affectedFeatures"]],
                         ["m4-x2apic-preemption"])
        self.assertIn("tests/test_m4_preempt_frame.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_m4_preempt.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_ring3_entry_has_real_qemu_and_paging_oracles(self):
        report = summarize(validate(self.real), ["boot/user_entry.S"])
        self.assertEqual([item["feature"] for item in report["affectedFeatures"]],
                         ["m4-ring3-user-syscall", "m4-ring3-fault-containment",
                         "m5-romfs-user-executable", "m5-interactive-romfs-run",
                          "m5-x2apic-user-timeout"])
        self.assertIn("tests/test_user_pages.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_m4_user.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_ring3_fault_recovery_maps_host_and_native_guest_evidence(self):
        report = summarize(validate(self.real), ["boot/user_isolation.c"])
        self.assertEqual([item["feature"] for item in report["affectedFeatures"]],
                         ["m4-ring3-fault-containment"])
        self.assertIn("tests/test_isolation_policy.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_m4_isolation.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_new_user_irq_maps_host_and_real_qemu_evidence(self):
        report = summarize(validate(self.real), ["boot/user_preempt_switch.S"])
        self.assertEqual([x["feature"] for x in report["affectedFeatures"]],
                         ["m4-ring3-preemptive-survival", "m5-x2apic-user-timeout"])
        self.assertIn("tests/test_user_preempt_frame.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_m4_user_fault_preempt.py",
                      report["affectedFeatures"][0]["fieldEvidence"])

    def test_changed_m3_c_source_maps_native_regressions(self):
        report = summarize(validate(self.real), ["boot/page_pool.c"])
        self.assertEqual(report["affectedFeatures"][0]["feature"], "m3-memory-bootstrap")
        self.assertIn("tests/test_m3_memory.py", report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_new_exception_idt_source_maps_real_cpu_fault_evidence(self):
        report = summarize(validate(self.real), ["boot/exception_idt.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m4-pit-irq-pacing", "m3-exception-idt",
             "m3-owned-fault-recovery", "m3-tss-ist",
             "m4-x2apic-preemption", "m4-ring3-user-syscall",
             "m4-ring3-fault-containment",
             "m4-ring3-preemptive-survival",
             "m5-guarded-user-fault-recovery", "m5-x2apic-user-timeout"])
        m3_entry = next(item for item in report["affectedFeatures"]
                        if item["feature"] == "m3-exception-idt")
        self.assertIn("tests/test_exception_idt.py",
                      m3_entry["existingRegressionTests"])
        self.assertIn("scripts/test_exception_idt.py",
                      m3_entry["fieldEvidence"])
        self.assertEqual(m3_entry["automatedEvidence"], "not-run")

    def test_changed_private_paging_source_maps_real_cr3_and_pf_proof(self):
        report = summarize(validate(self.real), ["boot/paging_probe.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-private-paging", "m3-owned-fault-recovery",
             "m3-bounded-multipage"])
        self.assertIn("tests/test_paging_tables.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_paging_probe.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_owner_registry_maps_to_genuine_qemu_fault_recovery(self):
        report = summarize(validate(self.real), ["boot/frame_owner.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-owned-fault-recovery", "m3-bounded-multipage",
             "m4-ring3-fault-containment",
             "m4-ring3-preemptive-survival"])
        self.assertIn("tests/test_frame_owner.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_paging_recovery.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_ist_gdt_tss_sources_map_to_real_double_fault_controls(self):
        report = summarize(validate(self.real), ["boot/tss_ist.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-tss-ist", "m4-ring3-user-syscall",
             "m4-ring3-fault-containment",
             "m4-ring3-preemptive-survival"])
        self.assertIn("tests/test_tss_ist.py",
                      report["affectedFeatures"][0]["existingRegressionTests"])
        self.assertIn("scripts/test_tss_ist.py",
                      report["affectedFeatures"][0]["fieldEvidence"])
        self.assertEqual(report["affectedFeatures"][0]["automatedEvidence"], "not-run")

    def test_bounded_multipage_pte_source_maps_native_and_qemu_proof(self):
        report = summarize(validate(self.real), ["boot/paging_tables.c"])
        self.assertEqual(
            [item["feature"] for item in report["affectedFeatures"]],
            ["m3-private-paging", "m3-bounded-multipage"])
        item = report["affectedFeatures"][1]
        self.assertIn("tests/test_paging_tables.py", item["existingRegressionTests"])
        self.assertIn("scripts/test_multimap.py", item["fieldEvidence"])
        self.assertEqual(item["automatedEvidence"], "not-run")

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
