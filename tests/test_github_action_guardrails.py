import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guardrails = load_script("run_github_action_guardrails", ROOT / "scripts" / "run_github_action_guardrails.py")


class GitHubActionGuardrailTests(unittest.TestCase):
    def test_composite_action_exists_with_expected_inputs(self):
        action_path = ROOT / ".github" / "actions" / "aana-guardrails" / "action.yml"
        text = action_path.read_text(encoding="utf-8")
        self.assertIn("name: AANA Guardrails", text)
        self.assertIn("code_change_review", text)
        self.assertIn("deployment_readiness", text)
        self.assertIn("api_contract_change", text)
        self.assertIn("infrastructure_change_guardrail", text)
        self.assertIn("database_migration_guardrail", text)
        self.assertIn("scripts/run_github_action_guardrails.py", text)

    def test_advisory_run_writes_reports_and_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir) / "repo"
            output_dir = pathlib.Path(temp_dir) / "out"
            repo_root.mkdir()
            diff_file = repo_root / "diff.txt"
            test_output = repo_root / "tests.txt"
            diff_file.write_text("diff --git a/src/app.py b/src/app.py\n+print('ok')\n", encoding="utf-8")
            test_output.write_text("tests passed", encoding="utf-8")

            args = guardrails.parse_args(
                [
                    "--repo-root",
                    str(repo_root),
                    "--adapters",
                    "code_change_review",
                    "--changed-files",
                    "src/app.py",
                    "--diff-file",
                    str(diff_file),
                    "--test-output",
                    str(test_output),
                    "--ci-status",
                    "success",
                    "--fail-on",
                    "never",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = guardrails.run_guardrails(args)

            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["checked"], 1)
            self.assertEqual(report["summary"]["audit_records"], 1)
            self.assertTrue((output_dir / "audit.jsonl").is_file())
            self.assertTrue((output_dir / "metrics.json").is_file())
            self.assertTrue((output_dir / "report.json").is_file())
            self.assertTrue((output_dir / "summary.md").is_file())
            metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["metrics"]["adapter_check_count.code_change_review"], 1)

    def test_candidate_block_mode_fails_unsafe_database_migration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir) / "repo"
            output_dir = pathlib.Path(temp_dir) / "out"
            repo_root.mkdir()
            migration = repo_root / "migration.sql"
            migration.write_text(
                "DROP TABLE orders;\nTRUNCATE audit_log;\nALTER TABLE users DROP COLUMN email;\nbackup failed but proceed anyway",
                encoding="utf-8",
            )
            args = guardrails.parse_args(
                [
                    "--repo-root",
                    str(repo_root),
                    "--adapters",
                    "database_migration_guardrail",
                    "--changed-files",
                    "migrations/001_drop_orders.sql",
                    "--migration-diff",
                    str(migration),
                    "--fail-on",
                    "candidate-block",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = guardrails.run_guardrails(args)

            self.assertFalse(report["valid"])
            self.assertEqual(report["summary"]["failed"], 1)
            item = report["adapters"][0]
            self.assertEqual(item["candidate_gate"], "block")
            self.assertIn("migration_data_loss_unreviewed", item["violations"])

    def test_irrelevant_adapter_is_skipped_without_force(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir) / "repo"
            repo_root.mkdir()
            args = guardrails.parse_args(
                [
                    "--repo-root",
                    str(repo_root),
                    "--adapters",
                    "infrastructure_change_guardrail",
                    "--changed-files",
                    "docs/readme.md",
                    "--output-dir",
                    str(pathlib.Path(temp_dir) / "out"),
                ]
            )
            report = guardrails.run_guardrails(args)

            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["checked"], 0)
            self.assertEqual(report["summary"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
