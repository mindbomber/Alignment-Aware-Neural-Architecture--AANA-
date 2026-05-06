import argparse
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from scripts import run_internal_pilot


class FakeProcess:
    stdout = None

    def __init__(self):
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class InternalPilotRunnerTests(unittest.TestCase):
    def test_runtime_paths_use_manifest_jsonl_sink(self):
        manifest = {
            "audit": {
                "sink": "jsonl://C:/ProgramData/AANA/audit/aana-audit.jsonl",
            }
        }

        paths = run_internal_pilot.runtime_paths(manifest)

        self.assertEqual(paths["audit_log"], pathlib.Path("C:/ProgramData/AANA/audit/aana-audit.jsonl"))
        self.assertEqual(paths["audit_dir"], pathlib.Path("C:/ProgramData/AANA/audit"))
        self.assertEqual(paths["integrity_manifest_dir"], pathlib.Path("C:/ProgramData/AANA/audit/manifests"))

    def test_setup_runtime_directories_creates_audit_log_and_manifest_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit" / "pilot.jsonl"
            paths = {
                "audit_log": audit_log,
                "audit_dir": audit_log.parent,
                "integrity_manifest_dir": audit_log.parent / "manifests",
            }

            created = run_internal_pilot.setup_runtime_directories(paths)

            self.assertTrue(audit_log.exists())
            self.assertTrue((audit_log.parent / "manifests").is_dir())
            self.assertIn(str(audit_log), created)

    def test_audit_integrity_manifest_path_uses_runtime_manifest_dir(self):
        audit_log = pathlib.Path("eval_outputs/audit/aana-internal-pilot.jsonl")
        paths = {
            "audit_log": audit_log,
            "audit_dir": audit_log.parent,
            "integrity_manifest_dir": audit_log.parent / "manifests",
        }

        manifest_path = run_internal_pilot.audit_integrity_manifest_path(paths)

        self.assertEqual(manifest_path, pathlib.Path("eval_outputs/audit/manifests/aana-internal-pilot-integrity.json"))

    def test_audit_metrics_path_defaults_to_runtime_audit_dir(self):
        audit_log = pathlib.Path("eval_outputs/audit/aana-internal-pilot.jsonl")
        paths = {
            "audit_log": audit_log,
            "audit_dir": audit_log.parent,
            "integrity_manifest_dir": audit_log.parent / "manifests",
        }

        metrics_path = run_internal_pilot.audit_metrics_path(paths)
        override_path = run_internal_pilot.audit_metrics_path(paths, "custom/metrics.json")

        self.assertEqual(metrics_path, pathlib.Path("eval_outputs/audit/aana-internal-pilot-metrics.json"))
        self.assertEqual(override_path, pathlib.Path("custom/metrics.json"))

    def test_resolve_token_uses_env_token(self):
        with mock.patch.dict("os.environ", {"AANA_BRIDGE_TOKEN": "test-token"}):
            token, generated = run_internal_pilot.resolve_token()

        self.assertEqual(token, "test-token")
        self.assertFalse(generated)

    def test_resolve_token_can_require_env_token(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(run_internal_pilot.PilotRunnerError):
                run_internal_pilot.resolve_token(require_env_token=True)

    def test_start_bridge_passes_audit_log_to_server(self):
        with mock.patch("subprocess.Popen") as popen:
            run_internal_pilot.start_bridge(
                "127.0.0.1",
                8765,
                pathlib.Path("examples/adapter_gallery.json"),
                1_048_576,
                "secret-token",
                pathlib.Path("eval_outputs/audit/pilot.jsonl"),
                shadow_mode=True,
            )

        command = popen.call_args.args[0]
        self.assertIn("--audit-log", command)
        self.assertIn("eval_outputs\\audit\\pilot.jsonl", command)
        self.assertIn("--shadow-mode", command)

    def test_pilot_rollout_defaults_to_shadow_mode(self):
        manifest = run_internal_pilot.load_json(run_internal_pilot.DEFAULT_MANIFEST)

        rollout = run_internal_pilot.pilot_rollout(manifest)
        phase = run_internal_pilot.pilot_phase(manifest)

        self.assertEqual(rollout["default_phase"], "shadow_mode")
        self.assertFalse(rollout["autonomous_enforcement_allowed"])
        self.assertEqual(phase["phase"], "shadow_mode")
        self.assertTrue(run_internal_pilot.phase_shadow_mode_enabled(phase))

    def test_run_pilot_writes_integrity_manifest_and_metrics_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            audit_log = temp_root / "audit" / "pilot.jsonl"
            metrics_output = temp_root / "handoff" / "metrics.json"
            deployment_manifest = temp_root / "deployment.json"
            deployment_manifest.write_text(
                json.dumps(
                    {
                        "pilot_rollout": {
                            "default_phase": "shadow_mode",
                            "autonomous_enforcement_allowed": False,
                            "phase_sequence": [
                                {
                                    "phase": "shadow_mode",
                                    "order": 1,
                                    "mode": "shadow",
                                    "enforcement": "observe_only",
                                }
                            ],
                        },
                        "bridge": {"host": "127.0.0.1", "max_body_bytes": 2048},
                        "audit": {"sink": f"jsonl://{audit_log}"},
                    }
                ),
                encoding="utf-8",
            )

            def fake_smoke(smoke_args):
                pathlib.Path(smoke_args.audit_log).write_text(
                    json.dumps(
                        {
                            "audit_record_version": "0.1",
                            "record_type": "agent_check",
                            "adapter_id": "support_reply",
                            "gate_decision": "pass",
                            "recommended_action": "revise",
                            "violation_codes": ["private_account_detail"],
                            "aix": {
                                "score": 1.0,
                                "decision": "accept",
                                "hard_blockers": [],
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return {
                    "status": "pass",
                    "agent_check": {
                        "candidate_gate": "block",
                        "gate_decision": "pass",
                        "recommended_action": "revise",
                    },
                    "audit": {"summary": {"total": 1}},
                }

            args = argparse.Namespace(
                deployment_manifest=deployment_manifest,
                event=pathlib.Path("examples/agent_event_support_reply.json"),
                gallery=pathlib.Path("examples/adapter_gallery.json"),
                host=None,
                port=8765,
                audit_log=None,
                metrics_output=metrics_output,
                max_body_bytes=None,
                require_env_token=False,
                timeout=1,
                pilot_phase=None,
                json=False,
            )
            process = FakeProcess()
            with mock.patch.object(run_internal_pilot, "start_bridge", return_value=process), mock.patch.object(
                run_internal_pilot.pilot_smoke_test, "wait_for_health"
            ), mock.patch.object(run_internal_pilot.pilot_smoke_test, "run_smoke_test", side_effect=fake_smoke):
                result = run_internal_pilot.run_pilot(args)

            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["pilot_phase"]["phase"], "shadow_mode")
            self.assertTrue(result["pilot_phase"]["shadow_mode"])
            self.assertFalse(result["pilot_phase"]["autonomous_enforcement_allowed"])
            self.assertTrue(process.terminated)
            self.assertTrue(pathlib.Path(result["runtime"]["integrity_manifest"]).exists())
            self.assertEqual(result["runtime"]["metrics"], str(metrics_output))
            self.assertEqual(result["runtime"]["metrics_version"], "0.1")
            self.assertEqual(result["runtime"]["metrics_record_count"], 1)
            metrics = json.loads(metrics_output.read_text(encoding="utf-8"))
            self.assertEqual(metrics["metrics"]["gate_decision_count.pass"], 1)
            self.assertEqual(metrics["metrics"]["aix_decision_count.accept"], 1)


if __name__ == "__main__":
    unittest.main()
