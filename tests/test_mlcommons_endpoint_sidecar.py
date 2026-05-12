import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import aana
from eval_pipeline import mlcommons_endpoint_sidecar


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MLCommonsEndpointSidecarTests(unittest.TestCase):
    def test_default_contract_validates_shadow_ready_not_live_ready(self):
        contract = mlcommons_endpoint_sidecar.default_endpoint_sidecar_contract()
        report = mlcommons_endpoint_sidecar.validate_endpoint_sidecar_contract(contract)

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["ready_for_shadow_benchmarking"])
        self.assertFalse(report["ready_for_live_endpoint_enforcement"])
        self.assertFalse(contract["pattern"]["runner_modification_required"])
        self.assertEqual(contract["pattern"]["default_mode"], "shadow")
        self.assertIn("not mlcommons benchmark certification", contract["claim_boundary"].lower())

    def test_checked_in_contract_validates(self):
        contract = mlcommons_endpoint_sidecar.load_endpoint_sidecar_contract(
            ROOT / "examples" / "mlcommons_endpoint_sidecar_contract.json"
        )
        report = mlcommons_endpoint_sidecar.validate_endpoint_sidecar_contract(contract)

        self.assertTrue(report["valid"], report)
        self.assertEqual(contract["endpoint_precheck_contract"]["schema_version"], "aana.mlcommons_endpoint_precheck.v1")

    def test_contract_requires_fail_closed_live_policy(self):
        contract = mlcommons_endpoint_sidecar.default_endpoint_sidecar_contract()
        contract["fail_closed_policy"]["direct_forward_requires"]["recommended_action"] = "revise"

        report = mlcommons_endpoint_sidecar.validate_endpoint_sidecar_contract(contract)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("fail_closed_policy.direct_forward_requires.recommended_action", paths)

    def test_contract_requires_latency_and_throughput_impact_fields(self):
        contract = mlcommons_endpoint_sidecar.default_endpoint_sidecar_contract()
        contract["impact_fields"]["latency"]["required"].remove("overhead_p95_ms")
        contract["impact_fields"]["throughput"]["required"].remove("throughput_delta_percent")

        report = mlcommons_endpoint_sidecar.validate_endpoint_sidecar_contract(contract)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("impact_fields.latency.required", paths)
        self.assertIn("impact_fields.throughput.required", paths)

    def test_benchmark_run_metadata_and_impact_report(self):
        metadata = mlcommons_endpoint_sidecar.benchmark_run_metadata(
            run_id="run-1",
            benchmark_suite="mlcommons-endpoints",
            benchmark_version="0.1",
            scenario="offline",
            sut_endpoint_id="endpoint-1",
            model_id="model-1",
            started_at="2026-05-12T00:00:00+00:00",
        )
        impact = mlcommons_endpoint_sidecar.sidecar_impact_report(
            run_metadata=metadata,
            baseline_p50_ms=100,
            baseline_p95_ms=200,
            sidecar_p50_ms=112,
            sidecar_p95_ms=230,
            baseline_requests_per_second=50,
            sidecar_requests_per_second=45,
        )
        validation = mlcommons_endpoint_sidecar.validate_sidecar_impact_report(impact)

        self.assertTrue(metadata["redacted_fields_only"])
        self.assertEqual(impact["latency"]["overhead_p95_ms"], 30)
        self.assertEqual(impact["throughput"]["throughput_delta_percent"], -10)
        self.assertTrue(validation["valid"], validation)

    def test_cli_writes_readiness_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = pathlib.Path(directory) / "sidecar-readiness.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/aana_cli.py",
                    "mlcommons-endpoint-sidecar",
                    "--contract",
                    "examples/mlcommons_endpoint_sidecar_contract.json",
                    "--report",
                    str(report_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["validation"]["valid"], payload)
            self.assertTrue(report_path.exists())

    def test_python_sdk_exports_endpoint_sidecar_helpers(self):
        self.assertTrue(callable(aana.default_endpoint_sidecar_contract))
        self.assertTrue(callable(aana.endpoint_precheck_contract))
        self.assertTrue(callable(aana.sidecar_impact_report))
        self.assertEqual(aana.MLCOMMONS_ENDPOINT_SIDECAR_VERSION, mlcommons_endpoint_sidecar.MLCOMMONS_ENDPOINT_SIDECAR_VERSION)


if __name__ == "__main__":
    unittest.main()
