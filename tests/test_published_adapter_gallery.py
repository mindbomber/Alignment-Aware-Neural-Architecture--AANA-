import json
import pathlib
import unittest

from eval_pipeline import adapter_gallery, agent_server


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublishedAdapterGalleryTests(unittest.TestCase):
    def test_published_gallery_cards_expose_selection_metadata(self):
        payload = adapter_gallery.published_gallery()

        self.assertEqual(payload["published_gallery_version"], "0.1")
        self.assertEqual(payload["adapter_count"], 43)
        self.assertIn("not production certification", payload["production_positioning"])
        self.assertIn("support", payload["product_lines"])
        self.assertEqual(
            set(payload["filters"]["risk_tiers"]),
            {"standard", "elevated", "high", "strict"},
        )
        self.assertIn("GitHub Action", payload["filters"]["surfaces"])
        self.assertIn("Local desktop/browser demo", payload["filters"]["surfaces"])
        self.assertIn("enterprise", payload["filters"]["packs"])
        self.assertIn("enterprise", payload["filters"]["families"])
        self.assertIn("developer", payload["filters"]["roles"])
        self.assertIn("try.ready", payload["readiness_counts"])
        self.assertEqual(
            set(payload["filters"]["readiness_statuses"]),
            {"demo_adapter", "pilot_ready", "production_candidate"},
        )

        required_fields = {
            "id",
            "title",
            "product_line",
            "workflow",
            "readiness_status",
            "risk_tier",
            "aix",
            "aix_tuning",
            "required_evidence",
            "evidence_requirements",
            "verifier_behavior",
            "correction_policy_summary",
            "human_review_path",
            "human_review_requirements",
            "supported_surfaces",
            "families",
            "roles",
            "readiness",
            "example_inputs",
            "example_outputs",
            "search_text",
        }
        for card in payload["adapters"]:
            self.assertTrue(required_fields.issubset(card), card["id"])
            self.assertIn(card["readiness_status"], {"demo_adapter", "pilot_ready", "production_candidate"}, card["id"])
            self.assertIn(card["risk_tier"], {"standard", "elevated", "high", "strict"})
            self.assertIsInstance(card["required_evidence"], list, card["id"])
            self.assertTrue(card["supported_surfaces"], card["id"])
            self.assertTrue(card["families"], card["id"])
            self.assertIn("status", card["production"], card["id"])
            self.assertIn("claim", card["production"], card["id"])
            self.assertIn(card["readiness"]["try"], {"ready", "partial"}, card["id"])
            self.assertIn(card["readiness"]["pilot"], {"ready", "not_packaged"}, card["id"])
            self.assertIn("beta", card["aix"], card["id"])
            self.assertIn("beta", card["aix_tuning"], card["id"])
            self.assertIsInstance(card["aix"]["layer_weights"], dict, card["id"])
            self.assertIsInstance(card["aix"]["thresholds"], dict, card["id"])
            self.assertTrue(card["example_inputs"]["prompt"], card["id"])
            self.assertTrue(card["example_inputs"]["bad_candidate"], card["id"])
            self.assertIn("gate_decision", card["example_outputs"]["expected"], card["id"])
            if card["product_line"] == "support":
                self.assertIn("expected_actions", card["example_outputs"], card["id"])
                self.assertTrue(card["human_review_requirements"], card["id"])
            self.assertNotIn("\\", card["adapter_path"], card["id"])

    def test_high_value_adapter_cards_have_expected_evidence_surfaces_and_aix(self):
        payload = adapter_gallery.published_gallery()
        cards = {card["id"]: card for card in payload["adapters"]}

        email = cards["email_send_guardrail"]
        self.assertEqual(email["risk_tier"], "strict")
        self.assertGreaterEqual(email["aix"]["beta"], 1.5)
        self.assertIn("draft email", email["required_evidence"])
        self.assertIn("recipient metadata", email["required_evidence"])
        self.assertIn("user approval", email["required_evidence"])
        self.assertIn("Local desktop/browser demo", email["supported_surfaces"])
        self.assertIn("Enterprise starter/pilot pack", email["supported_surfaces"])
        self.assertIn("Personal productivity starter/pilot pack", email["supported_surfaces"])
        self.assertIn("support", email["roles"])
        self.assertEqual(email["product_line"], "support")
        self.assertIn("Agent Event Contract", email["supported_surfaces"])
        self.assertIn("Python SDK", email["supported_surfaces"])
        self.assertTrue(email["verifier_behavior"])
        self.assertTrue(email["correction_policy_summary"])
        self.assertTrue(email["human_review_path"])
        self.assertTrue(email["human_review_requirements"])
        self.assertEqual(
            set(email["example_outputs"]["expected_actions"]["allowed_actions"]),
            {"accept", "revise", "retrieve", "ask", "defer", "refuse"},
        )
        self.assertIn("personal_productivity", email["families"])
        self.assertEqual(email["readiness"]["try"], "ready")

        deployment = cards["deployment_readiness"]
        self.assertEqual(deployment["risk_tier"], "strict")
        self.assertIn("GitHub Action", deployment["supported_surfaces"])
        self.assertIn("Enterprise starter/pilot pack", deployment["supported_surfaces"])
        self.assertIn("developer", deployment["roles"])

        civic = cards["procurement_vendor_risk"]
        self.assertIn("Government/civic starter/pilot pack", civic["supported_surfaces"])
        self.assertIn("government_civic", civic["packs"])
        self.assertIn("analyst", civic["roles"])

    def test_generated_data_matches_builder_contract(self):
        generated = json.loads((ROOT / "docs" / "adapter-gallery" / "data.json").read_text(encoding="utf-8"))
        rebuilt = adapter_gallery.published_gallery()

        self.assertEqual(generated["published_gallery_version"], rebuilt["published_gallery_version"])
        self.assertEqual(generated["production_positioning"], rebuilt["production_positioning"])
        self.assertEqual(generated["adapter_count"], rebuilt["adapter_count"])
        self.assertEqual(generated["risk_tier_counts"], rebuilt["risk_tier_counts"])
        self.assertEqual(
            {card["id"] for card in generated["adapters"]},
            {card["id"] for card in rebuilt["adapters"]},
        )
        self.assertTrue(all("\\" not in card["adapter_path"] for card in generated["adapters"]))

    def test_static_gallery_is_synthetic_public_browser_surface(self):
        index = (ROOT / "docs" / "adapter-gallery" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "docs" / "adapter-gallery" / "app.js").read_text(encoding="utf-8")

        self.assertIn("AANA Adapter Gallery", index)
        self.assertIn('new URL("data.json", document.currentScript.src)', app)
        self.assertIn("fetch(dataUrl", app)
        self.assertIn("Try this adapter", app)
        self.assertIn("?adapter=", app)
        self.assertIn("new URLSearchParams(window.location.search)", app)
        self.assertIn('params.get("adapter")', app)
        self.assertIn('params.get("pack")', app)
        self.assertIn('params.get("role")', app)
        self.assertIn("risk", app)
        self.assertIn("readiness", app)
        self.assertIn("required_evidence", app)
        self.assertNotIn("Authorization", app)
        self.assertNotIn("localStorage", app)
        self.assertNotIn("/workflow-check", app)

    def test_http_bridge_serves_gallery_and_documents_routes(self):
        status, content_type, body = agent_server.playground_static_response("/adapter-gallery/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"AANA Adapter Gallery", body)

        status, content_type, body = agent_server.playground_static_response("/adapter-gallery/data.json")

        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertIn(b'"adapter_count": 43', body)

        status, payload = agent_server.route_request("GET", "/openapi.json")

        self.assertEqual(status, 200)
        self.assertIn("/adapter-gallery/", payload["paths"])
        self.assertIn("/adapter-gallery/data.json", payload["paths"])


if __name__ == "__main__":
    unittest.main()
