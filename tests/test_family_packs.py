import json
import pathlib
import unittest

from eval_pipeline import agent_server, family_packs
from scripts import build_family_pages


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FamilyPackTests(unittest.TestCase):
    def test_family_pack_data_defines_three_product_boundaries(self):
        payload = family_packs.family_packs()
        families = {pack["family_id"]: pack for pack in payload["families"]}

        self.assertEqual(set(families), {"enterprise", "personal_productivity", "government_civic"})
        self.assertIn("customer, code, deployment, data, access, billing", families["enterprise"]["boundary"])
        self.assertIn("send, schedule, delete, move, write, buy, publish, or cite", families["personal_productivity"]["boundary"])
        self.assertIn("Public-service, procurement, grant, records, privacy", families["government_civic"]["boundary"])

        self.assertEqual(families["enterprise"]["adapter_count"], 8)
        self.assertEqual(families["personal_productivity"]["adapter_count"], 7)
        self.assertEqual(families["government_civic"]["adapter_count"], 8)
        for pack in families.values():
            self.assertGreater(len(pack["required_evidence"]), 0)
            self.assertIn("command", pack["starter_kit"])
            self.assertTrue(pack["starter_kit"]["command"].startswith("python scripts/pilots/run_starter_pilot_kit.py --kit "))
            for adapter in pack["adapters"]:
                self.assertIn(adapter["risk_tier"], {"standard", "elevated", "high", "strict"})
                self.assertTrue(adapter["required_evidence"], adapter["id"])
                self.assertIn("expected", adapter["example_outputs"])

    def test_generated_family_pages_show_adapters_try_links_and_pilot_kits(self):
        expected = {
            "enterprise": "Enterprise AANA Pack",
            "personal-productivity": "Personal Productivity AANA Pack",
            "government-civic": "Government And Civic AANA Pack",
        }
        for slug, title in expected.items():
            page = (ROOT / "docs" / slug / "index.html").read_text(encoding="utf-8")
            self.assertIn(title, page)
            self.assertIn("Product Boundary", page)
            self.assertIn("Starter Pilot Kit", page)
            self.assertIn("Try this adapter", page)
            self.assertIn("/playground?adapter=", page)
            self.assertIn("Expected outcome", page)
            self.assertIn("Required evidence", page)
            self.assertIn("python scripts/pilots/run_starter_pilot_kit.py --kit", page)

        data = json.loads((ROOT / "docs" / "families" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["families"]), 3)

    def test_family_pages_are_served_by_http_bridge(self):
        for path, expected in [
            ("/enterprise", b"Enterprise AANA Pack"),
            ("/personal-productivity", b"Personal Productivity AANA Pack"),
            ("/government-civic", b"Government And Civic AANA Pack"),
            ("/families/family-pack.css", b".adapter-grid"),
            ("/families/data.json", b'"family_packs_version"'),
        ]:
            status, content_type, body = agent_server.playground_static_response(path)
            self.assertEqual(status, 200, path)
            self.assertIn(expected, body, path)
            self.assertTrue(content_type, path)

    def test_openapi_documents_family_pack_routes(self):
        schema = agent_server.openapi_schema()

        self.assertIn("/enterprise/", schema["paths"])
        self.assertIn("/personal-productivity/", schema["paths"])
        self.assertIn("/government-civic/", schema["paths"])
        self.assertIn("/families/data.json", schema["paths"])

    def test_build_family_pages_script_runs(self):
        self.assertEqual(build_family_pages.main([]), 0)


if __name__ == "__main__":
    unittest.main()
