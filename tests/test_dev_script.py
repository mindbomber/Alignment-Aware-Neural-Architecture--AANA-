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


dev = load_script("dev", ROOT / "scripts" / "dev.py")


class DevScriptTests(unittest.TestCase):
    def test_production_profiles_runs_internal_pilot_profile_guard(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.production_profiles()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("validate-gallery --run-examples" in command for command in joined))
        self.assertTrue(any("contract-freeze --evidence-registry examples/evidence_registry.json" in command for command in joined))
        self.assertTrue(any("aix-tuning" in command for command in joined))
        self.assertTrue(any("validate-deployment --deployment-manifest examples/production_deployment_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("validate-governance --governance-policy examples/human_governance_policy_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("validate-observability --observability-policy examples/observability_policy_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("validate-evidence-registry --evidence-registry examples/evidence_registry.json" in command for command in joined))
        self.assertTrue(any("evidence-integrations --evidence-registry examples/evidence_registry.json" in command for command in joined))
        self.assertTrue(any("agent-check --event examples/agent_event_support_reply.json" in command for command in joined))
        self.assertTrue(any("audit-metrics --audit-log" in command for command in joined))
        self.assertTrue(any("release-check --skip-local-check" in command for command in joined))
        self.assertTrue(any("--audit-log" in command for command in joined))

    def test_production_profiles_accepts_ci_artifact_paths(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "ci" / "aana-ci-audit.jsonl"
            metrics_output = pathlib.Path(temp_dir) / "ci" / "aana-ci-metrics.json"

            def capture(command):
                commands.append(command)

            with mock.patch.object(dev, "run", side_effect=capture):
                dev.production_profiles(audit_log=audit_log, metrics_output=metrics_output)

            metrics_commands = [command for command in commands if "audit-metrics" in command]
            release_commands = [command for command in commands if "release-check" in command]

            self.assertEqual(len(metrics_commands), 1)
            self.assertEqual(len(release_commands), 1)
            self.assertIn(str(audit_log), metrics_commands[0])
            self.assertIn(str(metrics_output), metrics_commands[0])
            self.assertIn(str(audit_log), release_commands[0])
            self.assertEqual(audit_log.read_text(encoding="utf-8"), "")

    def test_pilot_bundle_runs_e2e_bundle_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.pilot_bundle()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_e2e_pilot_bundle.py" in command for command in joined))

    def test_contract_freeze_runs_contract_freeze_command(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.contract_freeze()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/aana_cli.py contract-freeze" in command for command in joined))

    def test_pilot_eval_runs_evaluation_kit_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.pilot_eval()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_pilot_evaluation_kit.py" in command for command in joined))


if __name__ == "__main__":
    unittest.main()
