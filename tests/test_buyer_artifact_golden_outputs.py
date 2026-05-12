import json
import pathlib
import tempfile
import unittest

from eval_pipeline import aix_audit, enterprise_support_demo


ROOT = pathlib.Path(__file__).resolve().parents[1]


def markdown_headings(text):
    return [line.strip() for line in text.splitlines() if line.startswith("#")]


class BuyerArtifactGoldenOutputTests(unittest.TestCase):
    def test_aix_report_markdown_golden_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = aix_audit.run_enterprise_ops_aix_audit(output_dir=temp_dir)
            markdown = pathlib.Path(result["summary"]["aix_report_md"]).read_text(encoding="utf-8")

            self.assertEqual(
                markdown_headings(markdown),
                [
                    "# AANA AIx Report: Enterprise Ops Pilot",
                    "## Executive Summary",
                    "## AIx Summary",
                    "## Use-Case Scope",
                    "## Evidence And Coverage",
                    "## Failure Modes",
                    "## Tested Workflows",
                    "## Remediation Plan",
                    "## Evidence Appendix",
                    "## Human Review",
                    "## Monitoring Plan",
                    "## Limitations",
                ],
            )
            self.assertIn("Recommendation: `pilot_ready_with_controls`", markdown)
            self.assertIn("| Workflow | Surface | Adapter | Gate | Action | AIx | Blockers |", markdown)
            self.assertIn("- Redaction policy: No raw prompts, candidates, evidence text, outputs, safe responses, secrets, or private records are included.", markdown)
            self.assertIn("Pilot readiness is not production certification", markdown)

    def test_aix_report_json_golden_schema_surface(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = aix_audit.run_enterprise_ops_aix_audit(output_dir=temp_dir)
            report = json.loads(pathlib.Path(result["summary"]["aix_report_json"]).read_text(encoding="utf-8"))

            self.assertEqual(
                set(report),
                {
                    "aix_report_schema_version",
                    "audit_metadata",
                    "calibration_confidence",
                    "component_scores",
                    "created_at",
                    "deployment_recommendation",
                    "evidence_appendix",
                    "evidence_quality",
                    "executive_summary",
                    "failure_modes",
                    "hard_blockers",
                    "human_review_requirements",
                    "limitations",
                    "monitoring_plan",
                    "overall_aix",
                    "product",
                    "product_bundle",
                    "remediation_plan",
                    "report_type",
                    "risk_tier",
                    "tested_workflows",
                    "use_case_scope",
                    "verifier_coverage",
                },
            )
            self.assertEqual(report["report_type"], "aana_aix_report")
            self.assertEqual(report["product"], "AANA AIx Audit")
            self.assertEqual(report["product_bundle"], "enterprise_ops_pilot")
            self.assertEqual(report["use_case_scope"]["deployment_boundary"], "pilot_ready_evidence_only_not_production_certification")
            self.assertFalse(report["evidence_appendix"]["raw_payload_logged"])
            self.assertLessEqual(
                {
                    "average",
                    "minimum",
                    "maximum",
                    "decision_counts",
                    "hard_blocker_count",
                },
                set(report["overall_aix"]),
            )
            self.assertLessEqual(
                {
                    "adapter_count",
                    "adapter_check_count",
                    "violation_codes",
                },
                set(report["verifier_coverage"]),
            )
            self.assertIn("not production certification", " ".join(report["limitations"]).lower())

    def test_enterprise_dashboard_golden_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = aix_audit.run_enterprise_ops_aix_audit(output_dir=temp_dir)
            dashboard = json.loads(pathlib.Path(result["summary"]["enterprise_dashboard"]).read_text(encoding="utf-8"))

            self.assertEqual(
                set(dashboard),
                {
                    "adapter_breakdown",
                    "aix",
                    "base_dashboard",
                    "cards",
                    "created_at",
                    "enterprise_dashboard_version",
                    "gate_decisions",
                    "hard_blockers",
                    "product",
                    "product_bundle",
                    "recommended_actions",
                    "shadow_mode",
                    "source_of_truth",
                    "surface_breakdown",
                    "top_violations",
                },
            )
            self.assertEqual(dashboard["source_of_truth"], "redacted_audit_metrics")
            self.assertEqual(
                set(dashboard["cards"]),
                {
                    "aix_average",
                    "aix_max",
                    "aix_min",
                    "block_or_fail",
                    "fail",
                    "hard_blockers",
                    "pass",
                    "shadow_would_block",
                    "shadow_would_intervene",
                },
            )
            self.assertEqual(
                {item["id"] for item in dashboard["surface_breakdown"]},
                {"support_customer_communications", "data_access_controls", "devops_release_controls"},
            )

    def test_enterprise_support_demo_markdown_golden_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flow = enterprise_support_demo.run_enterprise_support_demo(output_dir=temp_dir, shadow_mode=True)
            markdown = pathlib.Path(flow["artifacts"]["demo_summary"]).read_text(encoding="utf-8")

            self.assertEqual(
                markdown_headings(markdown),
                [
                    "# AANA Enterprise Support Demo Flow",
                    "## Flow",
                    "### 1. Customer support reply",
                    "### 2. Email send",
                    "### 3. Ticket update",
                    "## Generated Artifacts",
                    "## Dashboard Snapshot",
                ],
            )
            self.assertIn("Wedge: `customer support + email send + ticket update`", markdown)
            self.assertIn("- Recommended action: `defer`", markdown)
            self.assertIn("- Redacted audit written: `true`", markdown)
            self.assertIn('"shadow_would_block": 1', markdown)

    def test_buyer_docs_golden_sections(self):
        docs = {
            "pilot_packet": (
                ROOT / "docs" / "aana-aix-audit-enterprise-ops-pilot-packet.md",
                [
                    "# AANA AIx Audit Enterprise Ops Pilot",
                    "## One-Page Overview",
                    "## What The Pilot Evaluates",
                    "## What The Buyer Receives",
                    "## What Pilot-Ready Means",
                    "## What It Does Not Certify",
                    "## Sample AIx Report",
                    "## Sample Dashboard JSON/Metrics",
                    "## 30/60/90 Day Rollout Plan",
                    "### Days 1-30: Synthetic Pilot And Scope Lock",
                    "### Days 31-60: Shadow Mode With Customer Evidence",
                    "### Days 61-90: Controlled Enforcement Decision",
                    "## Buyer Decision",
                ],
            ),
            "onboarding_templates": (
                ROOT / "docs" / "aana-aix-audit-customer-onboarding-templates.md",
                [
                    "# AANA AIx Audit Customer Onboarding Templates",
                    "## 1. Use-Case Intake",
                    "## 2. System Inventory",
                    "## 3. Connector Checklist",
                    "## 4. Risk-Tier Questionnaire",
                    "## 5. Domain-Owner Signoff",
                    "## 6. Human-Review Routing",
                    "## 7. Shadow-Mode Success Criteria",
                    "## 8. Incident Response Plan",
                ],
            ),
            "connector_readiness": (
                ROOT / "docs" / "enterprise-connector-readiness.md",
                [
                    "# AANA Enterprise Connector Readiness",
                    "## What The Layer Defines",
                    "## Default Safety Position",
                    "## Connector Summary",
                    "## Customer Implementation Flow",
                ],
            ),
            "support_demo": (
                ROOT / "docs" / "enterprise-support-demo-flow.md",
                [
                    "# AANA Enterprise Support Demo Flow",
                    "## What The Buyer Sees",
                ],
            ),
        }

        for name, (path, expected_headings) in docs.items():
            with self.subTest(name=name):
                text = path.read_text(encoding="utf-8")
                lower = text.lower()
                self.assertEqual(markdown_headings(text), expected_headings)
                self.assertIn("production", lower)
                self.assertTrue(
                    "not production certification" in lower
                    or "does not create production certification" in lower
                    or "does not certify production" in lower
                    or "production use requires" in lower
                )


if __name__ == "__main__":
    unittest.main()
