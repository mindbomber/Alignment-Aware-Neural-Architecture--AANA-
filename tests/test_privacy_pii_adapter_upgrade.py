import json
import subprocess
import sys
import unittest
from pathlib import Path

from eval_pipeline.adapter_runner.verifier_catalog import VERIFIER_REGISTRY
from eval_pipeline.adapter_runner.verifier_modules.privacy_pii import detect_pii, redact_pii


ROOT = Path(__file__).resolve().parents[1]


class PrivacyPiiAdapterUpgradeTests(unittest.TestCase):
    def test_detector_catches_core_and_multilingual_pii(self):
        text = "Correo: ana@example.es, telefono 212-555-0198, DOB: 1991-05-14, SSN 123-45-6789."
        categories = {match["category"] for match in detect_pii(text)}

        self.assertTrue({"email", "phone", "date_of_birth", "ssn"}.issubset(categories))

    def test_redaction_removes_sensitive_values(self):
        text = "Send to dana.lee@example.net and card 4111 1111 1111 1111."
        redacted = redact_pii(text)

        self.assertNotIn("dana.lee@example.net", redacted)
        self.assertNotIn("4111 1111 1111 1111", redacted)
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_CARD]", redacted)

    def test_false_positive_control_allows_public_contact_and_product_ids(self):
        public = "The public support inbox is support@example.com and public helpdesk line is 800-555-0100."
        product = "Product SKU AANA-2026-05 passed release 2.4.1."

        self.assertEqual(detect_pii(public), [])
        self.assertEqual(detect_pii(product), [])

    def test_privacy_adapter_is_registered(self):
        module = VERIFIER_REGISTRY.get("privacy_pii")
        report = module.run("", "Customer SSN 123-45-6789 should be posted.")

        self.assertIn("privacy_pii_redaction", module.supported_adapters)
        self.assertTrue(report["violations"])
        self.assertIn("private_identity_detail_exposed", report["correction_routes"])

    def test_eval_script_reports_required_metrics(self):
        output = ROOT / "eval_outputs" / "privacy_pii_adapter_upgrade_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_privacy_pii_adapter_eval.py",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        metrics = payload["metrics"]
        self.assertEqual(metrics["pii_recall"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)
        self.assertEqual(metrics["safe_allow_rate"], 1.0)
        self.assertEqual(metrics["redaction_correctness"], 1.0)
        self.assertEqual(metrics["route_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()

