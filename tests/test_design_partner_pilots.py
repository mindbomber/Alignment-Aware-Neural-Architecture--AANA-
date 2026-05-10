import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


design_pilots = load_script("run_design_partner_pilots", ROOT / "scripts" / "pilots" / "run_design_partner_pilots.py")


class DesignPartnerPilotTests(unittest.TestCase):
    def test_index_lists_required_controlled_pilot_categories(self):
        index = design_pilots.load_index(ROOT / "examples" / "design_partner_pilots" / "index.json")
        categories = {pilot["category"] for pilot in index["pilots"]}

        self.assertEqual(
            categories,
            {"enterprise", "developer_tooling", "personal_productivity", "government_civic"},
        )
        self.assertGreaterEqual(len(index["pilots"]), 3)
        self.assertLessEqual(len(index["pilots"]), 5)

    def test_each_pilot_declares_collection_plan(self):
        index = design_pilots.load_index(ROOT / "examples" / "design_partner_pilots" / "index.json")

        for pilot in index["pilots"]:
            self.assertGreaterEqual(len(pilot["workflows"]), 1)
            collection_plan = pilot["collection_plan"]
            self.assertTrue(collection_plan["failure_mode_prompts"])
            self.assertTrue(collection_plan["friction_prompts"])
            self.assertTrue(collection_plan["adoption_blocker_prompts"])

    def test_all_design_partner_pilots_run_and_write_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = design_pilots.parse_args(["--pilot", "all", "--output-root", temp_dir])
            report = design_pilots.run_selected(args)

            self.assertTrue(report["valid"], report)
            self.assertEqual(report["summary"]["pilots"], 4)
            self.assertEqual(report["summary"]["workflows"], 16)
            self.assertEqual(report["summary"]["audit_records"], 16)
            self.assertEqual(report["summary"]["feedback_attached"], 0)

            for pilot in report["pilots"]:
                output_dir = pathlib.Path(temp_dir) / pilot["pilot_id"]
                self.assertTrue((output_dir / "audit.jsonl").is_file())
                self.assertTrue((output_dir / "metrics.json").is_file())
                self.assertTrue((output_dir / "dashboard.json").is_file())
                self.assertTrue((output_dir / "aix_drift.json").is_file())
                self.assertTrue((output_dir / "audit_integrity_manifest.json").is_file())
                self.assertTrue((output_dir / "reviewer_report.md").is_file())
                self.assertTrue((output_dir / "workflow_batch.json").is_file())
                self.assertTrue((output_dir / "feedback_template.json").is_file())
                self.assertTrue((output_dir / "field_notes_template.md").is_file())

                metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
                self.assertEqual(metrics["record_count"], pilot["summary"]["workflows"])
                feedback_template = json.loads((output_dir / "feedback_template.json").read_text(encoding="utf-8"))
                self.assertEqual(feedback_template["pilot_id"], pilot["pilot_id"])
                self.assertIn("failure_modes", feedback_template)
                self.assertIn("friction_points", feedback_template)
                self.assertIn("adoption_blockers", feedback_template)

    def test_feedback_dir_attaches_partner_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as feedback_dir:
            feedback_path = pathlib.Path(feedback_dir) / "enterprise_support_ops.json"
            feedback_path.write_text(
                json.dumps(
                    {
                        "design_partner_feedback_version": "0.1",
                        "pilot_id": "enterprise_support_ops",
                        "pilot_decision": "continue",
                        "failure_modes": [{"workflow_id": "enterprise-crm-support-reply", "description": "Missing CRM field."}],
                        "friction_points": [{"surface": "docs", "description": "Setup step was unclear."}],
                        "adoption_blockers": [{"blocker_type": "security_review", "description": "Need approval."}],
                    }
                ),
                encoding="utf-8",
            )

            args = design_pilots.parse_args(
                [
                    "--pilot",
                    "enterprise_support_ops",
                    "--output-root",
                    temp_dir,
                    "--feedback-dir",
                    feedback_dir,
                ]
            )
            report = design_pilots.run_selected(args)

            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["feedback_attached"], 1)
            self.assertEqual(report["summary"]["failure_modes"], 1)
            self.assertEqual(report["summary"]["friction_points"], 1)
            self.assertEqual(report["summary"]["adoption_blockers"], 1)
            self.assertEqual(report["pilots"][0]["feedback_summary"]["pilot_decision"], "continue")


if __name__ == "__main__":
    unittest.main()
