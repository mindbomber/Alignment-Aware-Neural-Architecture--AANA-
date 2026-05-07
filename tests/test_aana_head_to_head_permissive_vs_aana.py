import importlib.util
import pathlib

from test_aana_external_agent_trace_noisy_evidence_eval import fixture_rows


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "aana_head_to_head_permissive_vs_aana.py"
    spec = importlib.util.spec_from_file_location("aana_head_to_head_permissive_vs_aana", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_head_to_head_runner_compares_permissive_baseline_to_aana(tmp_path, monkeypatch):
    module = load_script()
    monkeypatch.setattr(module, "build_external_rows", lambda *_args, **_kwargs: fixture_rows())

    report = module.run(
        tmp_path / "report.json",
        tmp_path / "dataset.json",
        tmp_path / "rows.json",
        "fixture",
        "train",
        3,
        57,
        "moderate",
    )

    assert report["comparison"]["baseline"] == "plain_permissive_agent_accepts_every_tool_call"
    assert report["plain_permissive_agent_metrics"]["fn"] == 1
    assert "aana_schema_gate_metrics" in report
    assert "aana_minus_plain_permissive_delta" in report
    assert report["head_to_head_rows"][0]["plain_permissive_agent"]["recommended_action"] == "accept"
    assert (tmp_path / "rows.json").exists()


def test_metric_delta_reports_percentage_point_changes():
    module = load_script()
    delta = module.metric_delta(
        {"accuracy_pct": 90.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 80.0},
        {"accuracy_pct": 50.0, "block_recall_pct": 0.0, "safe_allow_rate_pct": 100.0},
    )

    assert delta["accuracy_pct"] == 40.0
    assert delta["block_recall_pct"] == 100.0
    assert delta["safe_allow_rate_pct"] == -20.0
