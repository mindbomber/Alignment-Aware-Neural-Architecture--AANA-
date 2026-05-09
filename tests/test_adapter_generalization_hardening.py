import json
import pathlib

from eval_pipeline.adapter_generalization_config import (
    configured_set,
    load_adapter_generalization_config,
    validate_adapter_generalization_config,
)
from eval_pipeline.adapter_generalization_gate import load_manifest, validate_adapter_generalization_gate
from eval_pipeline.benchmark_fit_lint import validate_benchmark_fit_manifest
from eval_pipeline.pre_tool_call_gate import IDENTITY_BOUND_ARGUMENT_KEYS, READ_POLICY_TOOLS, RISKY_WRITE_HINTS


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_adapter_generalization_config_is_valid_and_used_by_runtime() -> None:
    config = load_adapter_generalization_config(ROOT / "examples/adapter_generalization_config.json")
    report = validate_adapter_generalization_config(config)

    assert report["valid"], report["issues"]
    assert READ_POLICY_TOOLS == configured_set("read_policy_tools")
    assert IDENTITY_BOUND_ARGUMENT_KEYS == configured_set("identity_bound_argument_keys")
    assert RISKY_WRITE_HINTS == configured_set("risky_write_hints")


def test_adapter_generalization_gate_validates_all_subgates() -> None:
    manifest = load_manifest(ROOT / "examples/adapter_generalization_manifest.json")
    report = validate_adapter_generalization_gate(manifest, root=ROOT, require_existing_artifacts=True)

    assert report["valid"], report["issues"]
    assert report["subreports"]["generalization_config"]["valid"]
    assert report["subreports"]["heldout_validation"]["valid"]
    assert report["subreports"]["benchmark_fit_lint"]["valid"]
    assert report["subreports"]["benchmark_reporting"]["valid"]


def test_benchmark_fit_lint_detects_probe_style_patterns(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "eval_pipeline" / "adapter_runner"
    source.mkdir(parents=True)
    (source / "general_adapter.py").write_text("allow_benchmark_probes = True\nanswer_key = {'x': 'y'}\n", encoding="utf-8")
    manifest = json.loads((ROOT / "examples/benchmark_fit_lint_manifest.json").read_text(encoding="utf-8"))
    manifest["policy"]["scan_include"] = ["eval_pipeline/adapter_runner/**/*.py"]
    manifest["policy"]["required_adapter_family_surfaces"] = ["eval_pipeline/adapter_runner/**/*.py"]
    manifest["policy"]["allowed_literal_paths"] = []

    report = validate_benchmark_fit_manifest(manifest, root=tmp_path)

    assert not report["valid"]
    assert report["finding_count"] >= 1
    assert any("probe-style" in issue["message"].lower() for issue in report["issues"])


def test_benchmark_fit_lint_keeps_probe_control_allowlist_narrow(tmp_path: pathlib.Path) -> None:
    allowed = tmp_path / "examples" / "tau2"
    disallowed = tmp_path / "eval_pipeline" / "adapter_runner"
    allowed.mkdir(parents=True)
    disallowed.mkdir(parents=True)
    (allowed / "aana_contract_agent.py").write_text("ALLOW_BENCHMARK_PROBES = False\n", encoding="utf-8")
    (disallowed / "runtime.py").write_text("ALLOW_BENCHMARK_PROBES = True\n", encoding="utf-8")
    manifest = json.loads((ROOT / "examples/benchmark_fit_lint_manifest.json").read_text(encoding="utf-8"))
    manifest["policy"]["scan_include"] = ["examples/tau2/*.py", "eval_pipeline/adapter_runner/**/*.py"]
    manifest["policy"]["required_adapter_family_surfaces"] = ["examples/tau2/*.py", "eval_pipeline/adapter_runner/**/*.py"]
    manifest["policy"]["allowed_literal_paths"] = []

    report = validate_benchmark_fit_manifest(manifest, root=tmp_path)

    assert not report["valid"]
    assert any(issue["path"] == "eval_pipeline/adapter_runner/runtime.py" for issue in report["issues"])
    assert not any(issue["path"] == "examples/tau2/aana_contract_agent.py" for issue in report["issues"])


def test_generalization_gate_rejects_training_split_for_adapter_improvement(tmp_path: pathlib.Path) -> None:
    manifest = json.loads((ROOT / "examples/adapter_heldout_validation.json").read_text(encoding="utf-8"))
    manifest["adapter_improvements"][0]["heldout_validation"]["split"] = "training"
    heldout_path = tmp_path / "heldout.json"
    heldout_path.write_text(json.dumps(manifest), encoding="utf-8")

    gate_manifest = json.loads((ROOT / "examples/adapter_generalization_manifest.json").read_text(encoding="utf-8"))
    gate_manifest["artifacts"]["heldout_validation_manifest"] = str(heldout_path)

    report = validate_adapter_generalization_gate(gate_manifest, root=ROOT, require_existing_artifacts=False)

    assert not report["valid"]
    assert any("training" in issue["message"].lower() or "tuning" in issue["message"].lower() for issue in report["issues"])
