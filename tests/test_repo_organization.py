import unittest
from pathlib import Path

from eval_pipeline.repo_organization import validate_repo_organization


ROOT = Path(__file__).resolve().parents[1]


class RepoOrganizationTests(unittest.TestCase):
    def test_current_repo_organization_is_valid(self):
        report = validate_repo_organization(root=ROOT)

        self.assertTrue(report["valid"], report["issues"])
        self.assertIn("validation", report["script_groups"])
        self.assertIn("docs/repo-organization.md", report["required_docs"])
        self.assertGreater(report["scanned_file_count"], 0)


if __name__ == "__main__":
    unittest.main()
