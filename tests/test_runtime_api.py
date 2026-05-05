import pathlib
import unittest

import aana
import eval_pipeline
from eval_pipeline import runtime


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeApiTests(unittest.TestCase):
    def test_eval_pipeline_exports_narrow_typed_runtime_surface(self):
        self.assertIn("check", eval_pipeline.__all__)
        self.assertIn("RuntimeResult", eval_pipeline.__all__)
        self.assertIn("AANAValidationError", eval_pipeline.__all__)
        self.assertNotIn("agent_api", eval_pipeline.__all__)

    def test_runtime_check_returns_versioned_result_object(self):
        result = eval_pipeline.check(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
            candidate="AANA improves productivity by 40% for all teams [Source C].",
            evidence=["Source A: AANA makes constraints explicit."],
            constraints=["Do not invent citations."],
            workflow_id="runtime-smoke-001",
        )

        self.assertIsInstance(result, runtime.RuntimeResult)
        self.assertEqual(result.api_version, runtime.RUNTIME_API_VERSION)
        self.assertEqual(result.contract_version, "0.1")
        self.assertEqual(result.kind, "workflow")
        self.assertTrue(result.passed)
        self.assertEqual(result.gate_decision, "pass")
        self.assertEqual(result.recommended_action, "revise")
        self.assertEqual(result.result.workflow_id, "runtime-smoke-001")
        self.assertEqual(result.aix["decision"], "accept")
        self.assertTrue(result.validation.valid)

        payload = result.to_dict()
        self.assertEqual(payload["api_version"], runtime.RUNTIME_API_VERSION)
        self.assertEqual(payload["result"]["workflow_id"], "runtime-smoke-001")

    def test_runtime_check_request_accepts_typed_request(self):
        request = eval_pipeline.WorkflowRequest(
            adapter="research_summary",
            request="Write a concise research brief. Use Source A only.",
            candidate="Unsupported claim [Source C].",
            evidence=["Source A: AANA makes constraints explicit."],
            constraints=["Use Source A only."],
        )

        result = eval_pipeline.check_request(request)

        self.assertIsInstance(result.result, eval_pipeline.WorkflowResult)
        self.assertEqual(result.result.adapter, "research_summary")
        self.assertEqual(result.result.recommended_action, "revise")

    def test_runtime_check_batch_returns_versioned_batch_result(self):
        result = eval_pipeline.check_batch_file(ROOT / "examples" / "workflow_batch_productive_work.json")

        self.assertIsInstance(result, runtime.RuntimeResult)
        self.assertEqual(result.kind, "workflow_batch")
        self.assertTrue(result.passed)
        self.assertIsInstance(result.result, eval_pipeline.WorkflowBatchResult)
        self.assertEqual(result.result.summary["total"], 3)
        self.assertEqual(result.to_dict()["result"]["summary"]["failed"], 0)

    def test_runtime_validation_error_is_predictable(self):
        with self.assertRaises(runtime.AANAValidationError) as raised:
            eval_pipeline.check_request({"request": "Draft a summary."})

        error = raised.exception
        self.assertIn("adapter", str(error))
        self.assertEqual(error.details["kind"], "workflow_request")
        self.assertFalse(error.report["valid"])
        self.assertEqual(error.to_dict()["type"], "AANAValidationError")

    def test_runtime_missing_file_error_is_predictable(self):
        with self.assertRaises(runtime.AANAInputError) as raised:
            eval_pipeline.check_file(ROOT / "examples" / "missing-workflow.json")

        error = raised.exception
        self.assertIn("does not exist", str(error))
        self.assertEqual(error.details["path"], str(ROOT / "examples" / "missing-workflow.json"))
        self.assertEqual(error.to_dict()["api_version"], runtime.RUNTIME_API_VERSION)

    def test_aana_keeps_legacy_dict_helpers_and_exposes_typed_helpers(self):
        legacy = aana.check_file(ROOT / "examples" / "workflow_research_summary.json")
        typed = aana.check_file_typed(ROOT / "examples" / "workflow_research_summary.json")

        self.assertIsInstance(legacy, dict)
        self.assertIsInstance(typed, runtime.RuntimeResult)
        self.assertEqual(legacy["recommended_action"], typed.recommended_action)

    def test_runtime_schemas_alias_returns_public_schema_catalog(self):
        schemas = eval_pipeline.schemas()

        self.assertIn("workflow_request", schemas)
        self.assertIn("agent_event", schemas)
        self.assertIn("aix", schemas)


if __name__ == "__main__":
    unittest.main()
