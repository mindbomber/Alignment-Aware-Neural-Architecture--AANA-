import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_adapter_gallery = load_script(
    "validate_adapter_gallery", ROOT / "scripts" / "validate_adapter_gallery.py"
)

SUPPORT_ADAPTERS = {
    "support_reply",
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "invoice_billing_reply",
}
REQUIRED_SUPPORT_SURFACES = {
    "CLI",
    "Python SDK",
    "HTTP bridge",
    "Workflow Contract",
    "Agent Event Contract",
}


class AdapterGalleryTests(unittest.TestCase):
    def test_gallery_entries_declare_product_catalog_metadata(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        statuses = {entry.get("readiness") for entry in gallery["adapters"]}

        self.assertEqual(
            statuses,
            {"demo_adapter", "pilot_ready", "production_candidate"},
        )
        for entry in gallery["adapters"]:
            self.assertIn("family", entry, entry["id"])
            self.assertIn("risk_tier", entry, entry["id"])
            self.assertIn("evidence_requirements", entry, entry["id"])
            self.assertIn("supported_surfaces", entry, entry["id"])
            self.assertIn("production_status", entry, entry["id"])
            self.assertTrue(entry["family"], entry["id"])
            self.assertTrue(entry["evidence_requirements"], entry["id"])
            self.assertTrue(entry["supported_surfaces"], entry["id"])
            self.assertEqual(entry["production_status"]["level"], entry["readiness"], entry["id"])

    def test_support_adapters_are_productized_catalog_entries(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        support_line = gallery["product_lines"]["support"]
        entries = {entry["id"]: entry for entry in gallery["adapters"]}

        self.assertEqual(set(support_line["adapter_ids"]), SUPPORT_ADAPTERS)
        self.assertEqual(
            set(support_line["later_adapters"]),
            {"refunds", "account_closure", "chargeback", "cancellation", "escalation", "retention_deletion_request"},
        )
        self.assertIn("source-of-truth", support_line["source_of_truth"])
        self.assertTrue(
            {
                "readiness",
                "family",
                "risk_tier",
                "evidence_requirements",
                "supported_surfaces",
                "expected_actions",
                "aix_tuning",
                "caveats",
                "production_status",
                "docs_links",
                "copy_command",
                "human_review_requirements",
            }.issubset(support_line["catalog_contract"])
        )
        self.assertIn("customer-visible", support_line["boundary"])
        for adapter_id in SUPPORT_ADAPTERS:
            entry = entries[adapter_id]
            self.assertEqual(entry["product_line"], "support", adapter_id)
            self.assertTrue(entry["title"], adapter_id)
            self.assertTrue(REQUIRED_SUPPORT_SURFACES.issubset(entry["supported_surfaces"]), adapter_id)
            self.assertIn("support", entry["family"], adapter_id)
            self.assertEqual(entry["aix_tuning"]["risk_tier"], entry["risk_tier"], adapter_id)
            self.assertIn(entry["risk_tier"], {"standard", "elevated", "high", "strict"}, adapter_id)
            self.assertEqual(
                set(entry["expected_actions"]["allowed_actions"]),
                {"accept", "revise", "retrieve", "ask", "defer", "refuse"},
                adapter_id,
            )
            self.assertEqual(
                entry["expected_actions"]["golden_recommended_action"],
                entry["expected"]["recommended_action"],
                adapter_id,
            )
            self.assertEqual(
                entry["expected_actions"]["golden_candidate_aix_decision"],
                entry["expected"]["candidate_aix_decision"],
                adapter_id,
            )
            self.assertTrue(entry["evidence_requirements"], adapter_id)
            self.assertTrue(entry["verifier_behavior"], adapter_id)
            self.assertTrue(entry["correction_policy_summary"], adapter_id)
            self.assertTrue(entry["human_review_path"], adapter_id)
            self.assertTrue(entry["human_review_requirements"], adapter_id)
            self.assertTrue(entry["caveats"], adapter_id)
            self.assertIn(entry["production_status"]["level"], {"demo_adapter", "pilot_ready", "production_candidate"}, adapter_id)

    def test_gallery_validates_and_runs_examples(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")

        report = validate_adapter_gallery.validate_gallery(gallery, run_examples=True)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)
        self.assertGreaterEqual(len(report["checked_examples"]), 3)

    def test_gallery_rejects_missing_adapter_path(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        broken = dict(gallery)
        broken["adapters"] = [dict(gallery["adapters"][0])]
        broken["adapters"][0]["adapter_path"] = "examples/missing_adapter.json"

        report = validate_adapter_gallery.validate_gallery(broken)

        self.assertFalse(report["valid"])
        self.assertTrue(any("does not exist" in issue["message"] for issue in report["issues"]))

    def test_gallery_rejects_missing_catalog_metadata(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        broken = dict(gallery)
        broken["adapters"] = [dict(gallery["adapters"][0])]
        del broken["adapters"][0]["production_status"]

        report = validate_adapter_gallery.validate_gallery(broken)

        self.assertFalse(report["valid"])
        self.assertTrue(any("production_status" in issue["path"] for issue in report["issues"]))

    def test_gallery_rejects_broken_docs_links(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        broken = dict(gallery)
        broken["adapters"] = [dict(gallery["adapters"][0])]
        broken["adapters"][0]["docs_links"] = ["docs/missing-catalog-page.md"]

        report = validate_adapter_gallery.validate_gallery(broken)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Docs link does not resolve" in issue["message"] for issue in report["issues"]))

    def test_gallery_reports_catalog_completeness(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")

        report = validate_adapter_gallery.validate_gallery(gallery)

        self.assertEqual(report["catalog_completeness"]["score"], 1.0)
        self.assertEqual(report["catalog_completeness"]["weak_entry_count"], 0)
        self.assertEqual(
            set(report["catalog_completeness"]["readiness_counts"]),
            {"demo_adapter", "pilot_ready", "production_candidate"},
        )


if __name__ == "__main__":
    unittest.main()
