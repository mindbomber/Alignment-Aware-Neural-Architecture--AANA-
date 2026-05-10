import json
import subprocess
import sys
import unittest
from pathlib import Path

from eval_pipeline.adapter_runner.verifier_catalog import VERIFIER_REGISTRY
from eval_pipeline.adapter_runner.verifier_modules.privacy_pii import detect_pii, redact_pii
from eval_pipeline.adapter_runner.verifier_modules.privacy_pii_v2 import detect_pii_v2


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

    def test_detector_catches_cue_based_identity_and_account_fields(self):
        text = (
            "Name des Antragstellers: Come Krepek Cesarotti. "
            "The account number: 87425693 and bank routing number, 271210785 are present. "
            "The паспорт 504937505 and лична карта 815205340 are also present. "
            "Alter: 36 Jahre. Geschlecht: F. Adresse: Alst 341. Postleitzahl: 42349. "
            "Ort: Gernsheim. Telefon: 011 8638.3038."
        )
        categories = {match["category"] for match in detect_pii(text)}

        self.assertTrue(
            {
                "person_name",
                "account_number",
                "bank_routing_number",
                "passport",
                "national_id",
                "age",
                "gender",
                "street_address",
                "postal_code",
                "location",
                "phone",
            }.issubset(categories)
        )

    def test_detector_catches_multilingual_high_risk_identifier_fields(self):
        text = (
            "Veuillez fournir numéro d’assurance sociale 1.02.06.03300.435.80 "
            "et pièce d’identité V1805704874577. "
            "Kyselylomake: Sosiaaliturvatunnus 160862-135W, Passin numero TR4320974. "
            "Bank Routing Number:** 658143276. "
            "Credit card, number 5275 1478 9562 3846."
        )
        categories = {match["category"] for match in detect_pii(text)}

        self.assertTrue(
            {
                "ssn",
                "national_id",
                "passport",
                "bank_routing_number",
                "credit_card",
            }.issubset(categories)
        )

    def test_contextual_high_risk_identifier_detection(self):
        text = (
            "Falls relevant, senden Sie Ihre WJ5049718 und H1-08-Q2Q0RUO-2 "
            "zur sicheren Identifikation. Επιπλέον, με το διαβατήριο αριθμού QR3409919 "
            "μπόρεσε να συμμετάσχει. Payments can be made with the credit card 4397593946794746."
        )
        categories = {match["category"] for match in detect_pii(text)}

        self.assertIn("national_id", categories)
        self.assertIn("passport", categories)
        self.assertIn("credit_card", categories)

    def test_contextual_national_id_overrides_phone_shaped_match(self):
        text = (
            "Loppuun 5021538253 on kerätyt tiedot, jotka voidaan tallentaa turvallisesti "
            "henkilöllisyyden tarkistusta varten."
        )
        matches = detect_pii(text)
        matching = [match for match in matches if match["text"] == "5021538253"]

        self.assertEqual([match["category"] for match in matching], ["national_id"])

    def test_contextual_national_id_uses_bulgarian_identity_context(self):
        text = (
            "За резервацията е необходимо да се предостави валиден документ за самоличност "
            "114629618 или 016086508 преди потвърждение."
        )
        categories = [match["category"] for match in detect_pii(text)]

        self.assertIn("national_id", categories)
        self.assertNotIn("phone", categories)

    def test_contextual_ssn_overrides_phone_or_national_id_shape(self):
        text = (
            "Фактурата съдържа данъчният номер 487650085 и осигурителният номер 160862135 "
            "за финансовата отчетност."
        )
        categories_by_text = {match["text"]: match["category"] for match in detect_pii(text)}

        self.assertEqual(categories_by_text["487650085"], "ssn")
        self.assertEqual(categories_by_text["160862135"], "ssn")

    def test_contextual_ssn_uses_explicit_social_insurance_cues(self):
        text = (
            "Предоставете копия за социална осигуровка 612345678 и данъчен номер 872345901 "
            "към документите."
        )
        matches = detect_pii(text)

        self.assertTrue(any(match["text"] == "612345678" and match["category"] == "ssn" for match in matches))
        self.assertTrue(any("872345901" in str(match["text"]) and match["category"] == "ssn" for match in matches))

    def test_v2_broad_token_categories_require_strong_shape(self):
        model = {
            "status": "trained",
            "field_cues": {},
            "token_min_probability": 0.0,
            "_token_model": type(
                "FakeTokenModel",
                (),
                {
                    "classes_": ["O", "email", "person_name"],
                    "predict": lambda self, features: ["person_name", "email"],
                    "predict_proba": lambda self, features: [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
                },
            )(),
        }
        detections = detect_pii_v2("Здравейте приятел. E-Mail folgt.", model=model)

        self.assertEqual(detections, [])

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
                "scripts/evals/run_privacy_pii_adapter_eval.py",
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

    def test_hf_experiment_fixture_reports_metrics_without_raw_pii(self):
        output = ROOT / "eval_outputs" / "privacy_pii_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/hf/run_privacy_pii_hf_experiment.py",
                "--mode",
                "fixture",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["experiment_id"], "privacy_pii_hf_validation_v1")
        self.assertEqual(payload["mode"], "fixture")
        self.assertIn("pii_recall", payload["metrics"])
        self.assertIn("multilingual_recall", payload["metrics"])
        self.assertEqual(payload["metrics"]["safe_allow_rate"], 1.0)
        first_row = payload["rows"][0]
        self.assertIn("text_sha256", first_row)
        self.assertIn("redacted_preview", first_row)
        self.assertNotIn("text", first_row)
        self.assertNotIn("dana.lee@example.net", json.dumps(payload))

    def test_privacy_pii_v2_uses_trained_span_cues(self):
        model = {"status": "trained", "field_cues": {"person_name": ["case owner"]}}
        detections = detect_pii_v2("Case owner: Jordan Ellis approved the note.", model=model)

        self.assertIn("person_name", {item["category"] for item in detections})

    def test_hf_experiment_accepts_v2_detector(self):
        model_path = ROOT / "eval_outputs" / "privacy_pii_v2_model.test.json"
        model_path.write_text(
            json.dumps({"status": "trained", "field_cues": {"person_name": ["case owner"]}}),
            encoding="utf-8",
        )
        output = ROOT / "eval_outputs" / "privacy_pii_hf_experiment_v2_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/hf/run_privacy_pii_hf_experiment.py",
                "--mode",
                "fixture",
                "--detector-version",
                "v2",
                "--v2-model",
                str(model_path),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["detector_version"], "v2")
        self.assertEqual(payload["v2_model_status"], "trained")

    def test_high_risk_category_analyzer_ranks_gaps(self):
        output = ROOT / "eval_outputs" / "privacy_pii_high_risk_category_report.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/evals/analyze_privacy_pii_high_risk_categories.py",
                "--input",
                "docs/evidence/peer_review/privacy_pii_hf_experiment_results_v2.json",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("high_risk_category_metrics", payload)
        self.assertIn("ranked_high_risk_gaps", payload)
        self.assertIn("next_target", payload)

    def test_safe_miss_inspector_masks_spans_and_keeps_only_cue_words(self):
        from scripts.evals.inspect_privacy_pii_misses import inspect_misses

        result_payload = {
            "experiment_id": "unit",
            "detector_version": "v2",
            "rows": [
                {
                    "id": "row-1",
                    "source_dataset": "unit/dataset",
                    "expected_categories": ["ssn"],
                    "detected_categories": ["phone"],
                    "language": "en",
                }
            ],
        }

        def fake_raw_rows(experiment, *, offset, max_rows_per_source):
            return {
                "row-1": {
                    "dataset": {
                        "dataset_name": "unit/dataset",
                        "text_field": "text",
                        "label_field": "entities",
                    },
                    "row": {
                        "text": "Submit tax number 123-45-6789 for social insurance review.",
                        "entities": [{"label": "SSN", "start": 18, "end": 29}],
                    },
                }
            }

        import scripts.evals.inspect_privacy_pii_misses as inspector

        original_loader = inspector._load_raw_rows
        inspector._load_raw_rows = fake_raw_rows
        try:
            payload = inspect_misses(
                result_payload=result_payload,
                experiment={"datasets": []},
                target_category="ssn",
                offset=0,
                max_rows_per_source=1,
                cue_window_chars=80,
            )
        finally:
            inspector._load_raw_rows = original_loader

        row = payload["rows"][0]
        self.assertEqual(row["expected_category"], "ssn")
        self.assertIn("tax", row["surrounding_cue_words"])
        self.assertIn("social", row["surrounding_cue_words"])
        self.assertNotIn("123", json.dumps(payload))
        self.assertNotIn("6789", json.dumps(payload))
        self.assertFalse(row["category_ambiguity_likely"])


if __name__ == "__main__":
    unittest.main()
