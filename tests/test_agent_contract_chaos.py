import unittest

from eval_pipeline.agent_contract_chaos import validate_agent_contract_chaos


class AgentContractChaosTests(unittest.TestCase):
    def test_agent_contract_and_fastapi_chaos_cases_pass(self):
        report = validate_agent_contract_chaos()

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["case_count"], 9)
        self.assertEqual(report["audit_record_count"], 8)


if __name__ == "__main__":
    unittest.main()
