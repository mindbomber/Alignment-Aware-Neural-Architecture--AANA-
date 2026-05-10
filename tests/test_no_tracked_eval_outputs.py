import unittest
from unittest.mock import patch

from scripts.validation.validate_no_tracked_eval_outputs import validate_no_tracked_eval_outputs


class NoTrackedEvalOutputsTests(unittest.TestCase):
    def test_current_repo_has_no_tracked_eval_outputs(self):
        report = validate_no_tracked_eval_outputs()

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["tracked_eval_outputs_count"], 0)

    def test_validator_blocks_tracked_eval_outputs(self):
        with patch("scripts.validation.validate_no_tracked_eval_outputs.tracked_eval_outputs", return_value=["eval_outputs/result.json"]):
            report = validate_no_tracked_eval_outputs()

        self.assertFalse(report["valid"])
        self.assertEqual(report["tracked_eval_outputs"], ["eval_outputs/result.json"])


if __name__ == "__main__":
    unittest.main()
