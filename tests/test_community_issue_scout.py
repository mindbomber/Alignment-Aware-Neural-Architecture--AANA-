import importlib.util
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scout = load_script("community_issue_scout", ROOT / "scripts" / "community_issue_scout.py")


class CommunityIssueScoutTests(unittest.TestCase):
    def test_scores_mechanistic_interpretability_issue_as_high_fit(self):
        issue = {
            "title": "Add mechanistic interpretability tracing benchmark",
            "body": "We need a reproducible eval with citations, evidence, tests, and clear benchmark criteria.",
            "html_url": "https://github.com/example/repo/issues/1",
            "repository_url": "https://api.github.com/repos/example/repo",
            "labels": [{"name": "help wanted"}],
        }

        candidate = scout.score_issue(issue)

        self.assertEqual(candidate["aana_fit"], "high")
        self.assertEqual(candidate["issue_family"], "mechanistic_interpretability")
        self.assertEqual(candidate["adapter"], "research_answer_grounding")
        self.assertIn("experiment artifacts", candidate["evidence_needed"])

    def test_scores_vague_issue_as_low_fit(self):
        issue = {
            "title": "Any ideas?",
            "body": "What should we build next?",
            "html_url": "https://github.com/example/repo/issues/2",
            "repository_url": "https://api.github.com/repos/example/repo",
            "labels": [],
        }

        candidate = scout.score_issue(issue)

        self.assertEqual(candidate["aana_fit"], "low")
        self.assertEqual(candidate["first_action"], "ask clarifying question")

    def test_fixture_mode_writes_ranked_candidates(self):
        fixture = {
            "items": [
                {
                    "title": "Any ideas?",
                    "body": "What should we build next?",
                    "html_url": "https://github.com/example/repo/issues/2",
                    "repository_url": "https://api.github.com/repos/example/repo",
                    "labels": [],
                },
                {
                    "title": "RAG hallucination citation eval",
                    "body": "Need help wanted tests for unsupported answers, source grounding, citations, and benchmark evidence.",
                    "html_url": "https://github.com/example/rag/issues/3",
                    "repository_url": "https://api.github.com/repos/example/rag",
                    "labels": [{"name": "good first issue"}],
                },
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = pathlib.Path(temp_dir) / "issues.json"
            fixture_path.write_text(scout.json.dumps(fixture), encoding="utf-8")

            candidates = scout.scout([], 5, fixture=fixture_path)

        self.assertEqual([item["aana_fit"] for item in candidates], ["high", "low"])
        self.assertEqual(candidates[0]["issue_family"], "rag_grounding")


if __name__ == "__main__":
    unittest.main()
