import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot_eval = load_script("run_pilot_evaluation_kit", ROOT / "scripts" / "run_pilot_evaluation_kit.py")


class PilotEvaluationKitTests(unittest.TestCase):
    def test_kit_declares_strongest_adapter_family_surfaces(self):
        kit = pilot_eval.load_kit(ROOT / "examples" / "pilot_evaluation_kit.json")
        packs = {pack["id"]: pack for pack in kit["packs"]}

        self.assertIn("enterprise", packs)
        self.assertIn("personal", packs)
        self.assertIn("civic_government", packs)
        for pack_id in ["enterprise", "personal", "civic_government"]:
            self.assertIn("pilot_surface", packs[pack_id])
            self.assertTrue(packs[pack_id]["pilot_surface"]["entrypoint"])

        enterprise_surfaces = {scenario["surface"] for scenario in packs["enterprise"]["scenarios"]}
        self.assertTrue(
            {
                "crm_support_reply",
                "email_send_guardrail",
                "ticket_update_checker",
                "data_export_guardrail",
                "access_permission_change",
                "code_change_review",
                "deployment_readiness",
                "incident_response_update",
            }.issubset(enterprise_surfaces)
        )

        personal_surfaces = {scenario["surface"] for scenario in packs["personal"]["scenarios"]}
        self.assertTrue(
            {
                "email_guardrail",
                "calendar_scheduling",
                "file_operation_guardrail",
                "purchase_booking_guardrail",
                "research_grounding",
            }.issubset(personal_surfaces)
        )

        civic_surfaces = {scenario["surface"] for scenario in packs["civic_government"]["scenarios"]}
        self.assertTrue(
            {
                "procurement_vendor_risk",
                "grant_application_review",
                "public_records_privacy_redaction",
                "policy_memo_grounding",
                "benefits_eligibility_triage",
            }.issubset(civic_surfaces)
        )

    def test_kit_runs_selected_pack_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            args = pilot_eval.parse_args(
                [
                    "--pack",
                    "public_data_rehearsal",
                    "--audit-log",
                    str(tmp_path / "audit" / "pilot-eval.jsonl"),
                    "--metrics-output",
                    str(tmp_path / "metrics" / "pilot-eval-metrics.json"),
                    "--report-output",
                    str(tmp_path / "reports" / "pilot-eval.md"),
                    "--json-report-output",
                    str(tmp_path / "reports" / "pilot-eval.json"),
                ]
            )

            report = pilot_eval.run_kit(args)

            self.assertTrue(report["valid"], report)
            self.assertEqual(report["summary"]["packs"], 1)
            self.assertEqual(report["summary"]["scenarios"], 3)
            self.assertEqual(report["summary"]["failed"], 0)
            self.assertEqual(report["summary"]["audit_records"], 3)
            self.assertTrue((tmp_path / "audit" / "pilot-eval.jsonl").exists())
            self.assertTrue((tmp_path / "metrics" / "pilot-eval-metrics.json").exists())
            self.assertTrue((tmp_path / "reports" / "pilot-eval.md").exists())
            self.assertTrue((tmp_path / "reports" / "pilot-eval.json").exists())
            markdown = (tmp_path / "reports" / "pilot-eval.md").read_text(encoding="utf-8")
            self.assertIn("AANA Pilot Evaluation Report", markdown)
            self.assertIn("Public Data Rehearsal", markdown)

    def test_kit_marks_expectation_mismatch_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            kit = json.loads((ROOT / "examples" / "pilot_evaluation_kit.json").read_text(encoding="utf-8"))
            kit["packs"] = [
                {
                    "id": "broken",
                    "title": "Broken Expectations",
                    "scenarios": [
                        {
                            "id": "broken_support_reply",
                            "adapter_id": "support_reply",
                            "source": "agent_event",
                            "event_path": "examples/agent_events/support_reply.json",
                            "expected": {"recommended_action": "accept"},
                        }
                    ],
                }
            ]
            kit_path = tmp_path / "broken-kit.json"
            kit_path.write_text(json.dumps(kit), encoding="utf-8")
            args = pilot_eval.parse_args(
                [
                    "--kit",
                    str(kit_path),
                    "--audit-log",
                    str(tmp_path / "pilot-eval.jsonl"),
                    "--report-output",
                    str(tmp_path / "pilot-eval.md"),
                    "--json-report-output",
                    str(tmp_path / "pilot-eval.json"),
                ]
            )

            report = pilot_eval.run_kit(args)

            self.assertFalse(report["valid"])
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertFalse(report["packs"][0]["scenarios"][0]["expectation_checks"]["recommended_action"])

    def test_main_returns_zero_for_valid_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            output = io.StringIO()
            with redirect_stdout(output):
                code = pilot_eval.main(
                    [
                        "--pack",
                        "public_data_rehearsal",
                        "--audit-log",
                        str(tmp_path / "pilot-eval.jsonl"),
                        "--report-output",
                        str(tmp_path / "pilot-eval.md"),
                        "--json-report-output",
                        str(tmp_path / "pilot-eval.json"),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn('"valid": true', output.getvalue())


if __name__ == "__main__":
    unittest.main()
