import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


solver = load_script("community_issue_solver", ROOT / "scripts" / "benchmarks" / "community_issue_solver.py")


class CommunityIssueSolverTests(unittest.TestCase):
    def test_builds_workflow_contract_with_publish_boundaries(self):
        candidate = {
            "source": "https://github.com/example/repo/issues/7",
            "repository": "example/repo",
            "problem": "OECD AI Risk Framework Integration",
            "aana_fit": "high",
            "issue_family": "alignment_evaluation",
            "target_pr_area": "authorization_checks",
            "target_pr_eligible": True,
            "adapter": "model_evaluation_release",
            "labels": ["help wanted"],
        }
        issue = {
            "title": "OECD AI Risk Framework Integration",
            "body": "Implement OECD risk storage, scoring, reports, API endpoints, tests, and docs.",
            "labels": [{"name": "help wanted"}],
        }
        draft = solver.draft_public_response(candidate, issue)

        contract = solver.build_workflow_contract(candidate, issue, draft)

        self.assertEqual(contract["adapter"], "research_answer_grounding")
        self.assertIn("AANA", contract["candidate"])
        self.assertIn("Do not claim AANA guarantees alignment", contract["constraints"][0])
        self.assertEqual(contract["metadata"]["target_pr_area"], "authorization_checks")
        self.assertTrue(contract["metadata"]["target_pr_eligible"])
        self.assertTrue(any("Only propose PRs where AANA directly improves" in item for item in contract["constraints"]))
        self.assertEqual(contract["metadata"]["publish_boundary"], "public_issue_comment_or_pr_plan_only_after_aana_accept")

    def test_select_candidates_skips_low_fit_and_filters_repository(self):
        candidates = [
            {"repository": "a/low", "aana_fit": "low", "source": "https://github.com/a/low/issues/1"},
            {"repository": "b/high", "aana_fit": "high", "target_pr_eligible": True, "source": "https://github.com/b/high/issues/2"},
            {"repository": "c/random", "aana_fit": "high", "target_pr_eligible": False, "source": "https://github.com/c/random/issues/3"},
        ]

        selected = solver.select_candidates(candidates, repository="b/high", limit=1)

        self.assertEqual(selected, [candidates[1]])

    def test_create_workpack_writes_files_without_gate(self):
        candidate = {
            "source": "https://github.com/example/repo/issues/7",
            "repository": "example/repo",
            "problem": "RAG hallucination citation eval",
            "aana_fit": "high",
            "issue_family": "rag_grounding",
            "target_pr_area": "groundedness_citation_verification",
            "target_pr_eligible": True,
            "adapter": "research_answer_grounding",
            "labels": ["help wanted"],
            "publish_boundary": "public issue evidence only",
        }
        issue = {
            "title": "RAG hallucination citation eval",
            "body": "Need tests for source grounding and unsupported answers.",
            "labels": [{"name": "help wanted"}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(solver, "fetch_issue", return_value=issue):
                result = solver.create_workpack(candidate, output_dir=temp_dir, run_gate=False)

            workpack = pathlib.Path(result["workpack_dir"])
            self.assertTrue((workpack / "workflow_contract.json").is_file())
            self.assertTrue((workpack / "issue_response_draft.md").is_file())
            self.assertTrue((workpack / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
