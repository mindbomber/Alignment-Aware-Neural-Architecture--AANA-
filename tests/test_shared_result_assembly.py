import json
import pathlib
import unittest

import aana
from eval_pipeline import agent_api, agent_server
from eval_pipeline.adapter_runner import results as result_assembly
from scripts import aana_cli


ROOT = pathlib.Path(__file__).resolve().parents[1]


PUBLIC_RESULT_KEYS = {
    "gate_decision",
    "recommended_action",
    "candidate_gate",
    "aix",
    "candidate_aix",
    "violations",
    "audit_summary",
}


def public_shape(result):
    return {
        "has_keys": {key: key in result for key in PUBLIC_RESULT_KEYS},
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_decision": result.get("aix", {}).get("decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
        "violation_codes": result_assembly.violation_codes(result.get("violations", [])),
        "audit_summary": result.get("audit_summary"),
    }


class SharedResultAssemblyTests(unittest.TestCase):
    def test_sdk_http_and_cli_workflow_results_share_public_shape(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")
        gallery = aana_cli.load_gallery(aana_cli.DEFAULT_GALLERY)
        entry = aana_cli.find_entry(gallery, workflow_request["adapter"])

        sdk_result = aana.check_request(workflow_request)
        status, http_result = agent_server.route_request(
            "POST",
            "/workflow-check",
            json.dumps(workflow_request).encode("utf-8"),
        )
        cli_result = aana_cli.run_entry(entry)

        self.assertEqual(status, 200)
        self.assertEqual(public_shape(sdk_result), public_shape(http_result))
        self.assertEqual(public_shape(sdk_result), public_shape(cli_result))

    def test_batch_items_use_same_workflow_result_shape(self):
        batch_request = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")

        batch_result = agent_api.check_workflow_batch(batch_request)

        self.assertEqual(batch_result["summary"], result_assembly.workflow_batch_summary(batch_result["results"]))
        for item in batch_result["results"]:
            self.assertTrue(PUBLIC_RESULT_KEYS.issubset(item))
            self.assertEqual(item["audit_summary"], result_assembly.audit_safe_summary(item))

    def test_audit_safe_summary_excludes_raw_text(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")

        result = agent_api.check_workflow_request(workflow_request)
        summary_json = json.dumps(result["audit_summary"], sort_keys=True)

        self.assertEqual(result["audit_summary"], result_assembly.audit_safe_summary(result))
        self.assertNotIn(workflow_request["request"], summary_json)
        self.assertNotIn(workflow_request["candidate"], summary_json)
        self.assertNotIn(result["output"], summary_json)

    def test_workflow_failure_result_uses_shared_shape(self):
        request = {"workflow_id": "bad-item", "adapter": "missing", "allowed_actions": ["defer"]}
        recommended_action, action_violation = agent_api.workflow_contract.safe_failure_action(
            request["allowed_actions"]
        )

        result = result_assembly.assemble_workflow_failure_result(
            request,
            ValueError("adapter missing"),
            contract_version=agent_api.WORKFLOW_CONTRACT_VERSION,
            recommended_action=recommended_action,
            action_violation=action_violation,
        )

        self.assertTrue(PUBLIC_RESULT_KEYS.issubset(result))
        self.assertEqual(result["gate_decision"], "fail")
        self.assertEqual(result["recommended_action"], "defer")
        self.assertEqual(result["audit_summary"], result_assembly.audit_safe_summary(result))


if __name__ == "__main__":
    unittest.main()

