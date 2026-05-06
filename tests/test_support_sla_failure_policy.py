import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "examples" / "support_sla_failure_policy.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


support_sla = load_script("validate_support_sla_failure_policy", ROOT / "scripts" / "validate_support_sla_failure_policy.py")


class SupportSlaFailurePolicyTests(unittest.TestCase):
    def test_policy_manifest_covers_required_fallbacks(self):
        report = support_sla.validate_support_sla_failure_policy(POLICY_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_fallbacks"]), set(support_sla.REQUIRED_FALLBACKS))
        self.assertEqual(report["fallback_count"], len(support_sla.REQUIRED_FALLBACKS))

    def test_required_fallback_routes_are_exact(self):
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        fallbacks = {item["id"]: item for item in payload["undecidable_fallbacks"]}

        self.assertEqual(set(fallbacks["evidence_unavailable"]["allowed_actions"]), {"retrieve", "ask"})
        self.assertEqual(fallbacks["crm_unavailable"]["default_action"], "defer")
        self.assertEqual(fallbacks["verification_missing"]["default_action"], "ask")
        self.assertEqual(fallbacks["privacy_risk"]["default_action"], "refuse")
        self.assertEqual(fallbacks["policy_ambiguity"]["default_action"], "defer")
        self.assertEqual(fallbacks["bridge_unavailable_irreversible"]["failure_mode"], "fail_closed")
        self.assertEqual(fallbacks["bridge_unavailable_irreversible"]["default_action"], "refuse")
        self.assertEqual(fallbacks["bridge_unavailable_draft"]["failure_mode"], "fail_advisory_when_mode_allows")

    def test_validator_rejects_weak_bridge_irreversible_policy(self):
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        for fallback in payload["undecidable_fallbacks"]:
            if fallback["id"] == "bridge_unavailable_irreversible":
                fallback["failure_mode"] = "fail_open"
                fallback["default_action"] = "accept"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = support_sla.validate_support_sla_failure_policy(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("bridge_unavailable_irreversible.failure_mode" in error for error in report["errors"]))
        self.assertTrue(any("bridge_unavailable_irreversible.default_action" in error for error in report["errors"]))

    def test_docs_state_required_fallbacks(self):
        doc = (ROOT / "docs" / "support-sla-failure-policy.md").read_text(encoding="utf-8")

        for phrase in (
            "Evidence unavailable -> `retrieve` or `ask`",
            "CRM unavailable -> `defer`",
            "Verification missing -> `ask`",
            "Privacy risk -> `refuse`",
            "Policy ambiguity -> `defer`",
            "Bridge unavailable for irreversible support actions -> fail closed",
            "Bridge unavailable for draft-only support responses -> fail advisory",
        ):
            self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()
