import json
import subprocess
import sys
import unittest
from pathlib import Path

from eval_pipeline.adapter_runner.verifier_catalog import VERIFIER_REGISTRY
from eval_pipeline.adapter_runner.verifier_modules.grounded_qa import (
    citation_tokens,
    classify_grounded_answer,
    grounded_qa_tool_report,
)


ROOT = Path(__file__).resolve().parents[1]


class GroundedQaAdapterUpgradeTests(unittest.TestCase):
    def test_classifies_supported_answer_with_indexed_citations(self):
        prompt = "Retrieved documents include Doc A. Citation index maps [Doc A]. Doc A says the pilot improved checklist completion."
        answer = "The pilot improved checklist completion. [Doc A]"
        output = classify_grounded_answer(prompt, answer)

        self.assertEqual(output["label"], "supported")
        self.assertEqual(citation_tokens(answer), {"[Doc A]"})

    def test_flags_unsupported_and_invalid_citation(self):
        prompt = "Retrieved documents include Doc A. Citation index maps [Doc A]. No source supports an 80% claim."
        answer = "The system guarantees 80% gains for all customers. [Doc C]"
        report = grounded_qa_tool_report(prompt, answer)
        codes = {violation["code"] for violation in report["violations"]}

        self.assertIn("grounded_qa_unsupported_claim", codes)
        self.assertIn("grounded_qa_invalid_citation", codes)

    def test_citation_optional_mode_uses_lexical_grounding(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: What happened? Retrieved evidence: Doc A says the pilot reduced duplicate tickets."
        )
        supported = classify_grounded_answer(prompt, "The pilot reduced duplicate tickets.")
        unsupported = classify_grounded_answer(prompt, "The pilot eliminated all compliance risk globally.")

        self.assertEqual(supported["label"], "supported")
        self.assertEqual(unsupported["label"], "unsupported")
        self.assertTrue(unsupported["lexical_support_gap"])

    def test_citation_optional_mode_checks_answer_shape(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Which team scored the longest field goal kick of the game?\n"
            "Retrieved evidence: Rams kicker Jeff Wilkins made a 41-yard field goal. Chiefs kicker Lawrence Tynes nailed a 42-yard field goal."
        )
        output = classify_grounded_answer(prompt, "['Rams', 'second', 'Marc Bulger', 'Kevin Curtis']")

        self.assertEqual(output["label"], "unsupported")
        self.assertTrue(output["answer_shape_gap"])

    def test_citation_optional_mode_checks_simple_numeric_consistency(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: How many more households are there than families?\n"
            "Retrieved evidence: There were 18,878 households and 13,629 families residing in the county."
        )

        self.assertEqual(classify_grounded_answer(prompt, "5249")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "19300")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["numeric_consistency_gap"])

    def test_citation_optional_mode_checks_yard_event_ranking(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: How many yards was the second longest field goal of the first half?\n"
            "Retrieved evidence: In the second quarter, Lawrence Tynes nailed a 42-yard field goal. "
            "Rams kicker Jeff Wilkins made a 41-yard field goal to end the half. "
            "In the third quarter, another play happened."
        )

        self.assertEqual(classify_grounded_answer(prompt, "41")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "42")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["numeric_consistency_gap"])

    def test_citation_optional_mode_checks_percent_not_variants(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: How many in percent from the census weren't Irish?\n"
            "Retrieved evidence: 13.1% Irish people were reported in the census."
        )

        self.assertEqual(classify_grounded_answer(prompt, "86.9")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "87.1")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["numeric_consistency_gap"])

    def test_citation_optional_mode_checks_explicit_count_cue(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: How many touchdowns did Crabtree catch?\n"
            "Retrieved evidence: Carr hit Michael Crabtree for his first of three touchdown scores on the day."
        )

        self.assertEqual(classify_grounded_answer(prompt, "3")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "2")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["numeric_consistency_gap"])

    def test_citation_optional_mode_checks_entity_comparison(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Which group from the census is smaller: German or Irish?\n"
            "Retrieved evidence: 22.5% were of German people, 13.1% Irish people, and 9.8% Italian people."
        )

        self.assertEqual(classify_grounded_answer(prompt, "Irish")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "German")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["entity_consistency_gap"])

    def test_citation_optional_mode_checks_winning_team_selection(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Which team won the game, Patriots or Packers?\n"
            "Retrieved evidence: The Patriots traveled to Lambeau Field to play the Green Bay Packers. "
            "With the win, the Patriots improved to 7-3."
        )

        self.assertEqual(classify_grounded_answer(prompt, "Patriots")["label"], "supported")
        wrong = classify_grounded_answer(prompt, "Packers")
        self.assertEqual(wrong["label"], "unsupported")
        self.assertTrue(wrong["entity_consistency_gap"])

    def test_citation_optional_mode_flags_introduced_named_entities(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Summarize the report.\n"
            "Retrieved evidence: Alice Hart joined Project Orion in 2020 after a public board vote."
        )

        supported = classify_grounded_answer(prompt, "Alice Hart joined Project Orion in 2020 after a board vote.")
        unsupported = classify_grounded_answer(
            prompt,
            "Alice Hart, Brian Cole, and Carol Reed joined Project Orion in 2020 after a board vote.",
        )

        self.assertEqual(supported["label"], "supported")
        self.assertEqual(unsupported["label"], "unsupported")
        self.assertTrue(unsupported["introduced_fact_gap"])
        self.assertGreaterEqual(unsupported["unsupported_proper_name_count"], 1)

    def test_citation_optional_mode_flags_introduced_numeric_facts_in_summaries(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Summarize the report.\n"
            "Retrieved evidence: The pilot included 12 participants and two follow-up interviews."
        )

        output = classify_grounded_answer(
            prompt,
            "The pilot included 12 participants, two follow-up interviews, 30 clinic sites, and 500 patient records.",
        )

        self.assertEqual(output["label"], "unsupported")
        self.assertTrue(output["introduced_fact_gap"])
        self.assertGreaterEqual(output["unsupported_numeric_fact_count"], 1)

    def test_citation_optional_mode_flags_evidence_contradictions(self):
        timing_prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Summarize the report.\n"
            "Retrieved evidence: The source says it is not clear when or where the suspect was arrested."
        )
        timing = classify_grounded_answer(timing_prompt, "The suspect was arrested on March 26.")

        numeric_prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Summarize the report.\n"
            "Retrieved evidence: Five people were infected and three died from the outbreak."
        )
        numeric = classify_grounded_answer(numeric_prompt, "Five people died from the outbreak.")

        self.assertEqual(timing["label"], "unsupported")
        self.assertTrue(timing["evident_contradiction_gap"])
        self.assertEqual(numeric["label"], "unsupported")
        self.assertTrue(numeric["evident_contradiction_gap"])

    def test_optional_semantic_verifier_tightens_grounded_qa_route(self):
        prompt = (
            "Citation optional. Use retrieved evidence as source. "
            "Question: Summarize the report.\n"
            "Retrieved evidence: The pilot reduced duplicate tickets."
        )

        def fake_semantic_verifier(_prompt, _answer):
            return {
                "label": "baseless",
                "route": "revise",
                "confidence": 0.91,
                "reason_codes": ["introduced_material_claim"],
                "evidence_issue": "baseless",
                "claims": [
                    {
                        "claim_id": "claim_1",
                        "label": "baseless",
                        "claim_type": "baseless_info",
                        "confidence": 0.91,
                        "reason_codes": ["introduced_material_claim"],
                    }
                ],
            }

        report = grounded_qa_tool_report(
            prompt,
            "The pilot reduced duplicate tickets and eliminated churn.",
            semantic_verifier=fake_semantic_verifier,
        )
        codes = {violation["code"] for violation in report["violations"]}
        semantic = report["checks"][0]["semantic_verifier"]

        self.assertIn("grounded_qa_semantic_unsupported", codes)
        self.assertEqual(report["correction_routes"]["grounded_qa_semantic_unsupported"], "revise")
        self.assertEqual(semantic["provider"], "injected")
        self.assertEqual(semantic["claim_level"]["unsupported_claim_types"], ["baseless_info"])
        self.assertFalse(semantic["raw_payload_logged"])

    def test_routes_unanswerable_high_impact_to_defer(self):
        prompt = "Evidence is insufficient and no source supports a patient-specific treatment choice. This is medical and high impact. Citation index maps [Doc A]."
        answer = "The patient should take Treatment X immediately because it always works. [Doc A]"
        report = grounded_qa_tool_report(prompt, answer)

        self.assertEqual(report["correction_routes"]["grounded_qa_high_impact_defer"], "defer")
        self.assertIn("grounded_qa_unanswerable_answered", report["correction_routes"])

    def test_grounded_qa_verifier_is_registered_for_research_answer_adapter(self):
        module = VERIFIER_REGISTRY.get("grounded_qa")

        self.assertIn("research_answer_grounding", module.supported_adapters)
        self.assertEqual(module.family, "grounded_qa")

    def test_eval_script_reports_required_metrics(self):
        output = ROOT / "eval_outputs" / "grounded_qa_adapter_upgrade_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_grounded_qa_adapter_eval.py",
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
        self.assertEqual(metrics["unsupported_claim_recall"], 1.0)
        self.assertEqual(metrics["answerable_safe_allow_rate"], 1.0)
        self.assertGreaterEqual(metrics["citation_evidence_coverage"], 0.8)
        self.assertEqual(metrics["over_refusal_rate"], 0.0)
        self.assertEqual(metrics["route_accuracy"], 1.0)

    def test_hf_experiment_script_reports_comparisons_without_raw_text(self):
        output = ROOT / "eval_outputs" / "grounded_qa_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_grounded_qa_hf_experiment.py",
                "--max-rows-per-source",
                "2",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["experiment_id"], "grounded_qa_v1_hf_validation")
        self.assertIn("base_accept_blindly", payload["comparisons"])
        self.assertIn("aana_groundedness_gate", payload["comparisons"])
        self.assertIn("aana_revise_defer_route", payload["comparisons"])
        first_row = payload["rows"][0]
        self.assertIn("question_sha256", first_row)
        self.assertIn("context_sha256", first_row)
        self.assertIn("answer_sha256", first_row)
        self.assertNotIn("prompt", first_row)
        self.assertNotIn("answer", first_row)

    def test_safe_miss_inspector_reports_clusters_without_raw_text(self):
        from scripts.inspect_grounded_qa_misses import inspect_misses

        result = {
            "experiment_id": "unit",
            "detector_version": "grounded_qa_v1",
            "rows": [
                {
                    "id": "case-1",
                    "source_dataset": "unit",
                    "schema": "halubench",
                    "question_sha256": "q",
                    "context_sha256": "c",
                    "answer_sha256": "a",
                    "expected_label": "unsupported",
                    "actual_label": "supported",
                    "expected_route": "revise",
                    "actual_route": "accept",
                }
            ],
        }

        import scripts.inspect_grounded_qa_misses as inspector

        original_loader = inspector.load_cases
        inspector.load_cases = lambda *, experiment, max_rows_per_source: [
            {
                "id": "case-1",
                "source_dataset": "unit",
                "schema": "halubench",
                "prompt": (
                    "Citation optional. Use retrieved evidence as source. "
                    "Question: How many more households are there than families? "
                    "Retrieved evidence: There were 18,878 households and 13,629 families."
                ),
                "answer": "19300",
                "unsupported": True,
            }
        ]
        try:
            payload = inspect_misses(
                result_payload=result,
                experiment={"datasets": []},
                max_rows_per_source=1,
            )
        finally:
            inspector.load_cases = original_loader

        self.assertEqual(payload["miss_count"], 1)
        row = payload["rows"][0]
        self.assertIn("numeric_reasoning", row["context_clusters"])
        self.assertIn("question_sha256", row)
        self.assertNotIn("prompt", json.dumps(payload))
        self.assertNotIn("18,878", json.dumps(payload))
        self.assertNotIn("19300", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
