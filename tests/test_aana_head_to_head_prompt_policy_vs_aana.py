import importlib.util
import pathlib

from test_aana_external_agent_trace_noisy_evidence_eval import fixture_rows


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "evals" / "aana_head_to_head_prompt_policy_vs_aana.py"
    spec = importlib.util.spec_from_file_location("aana_head_to_head_prompt_policy_vs_aana", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_policy_runner_compares_flattened_guardrail_to_aana(tmp_path, monkeypatch):
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

    assert report["comparison"]["baseline"] == "prompt_only_policy_guardrail_over_flattened_action_evidence_text"
    assert "prompt_only_policy_guardrail_metrics" in report
    assert "aana_schema_gate_metrics" in report
    assert "aana_minus_prompt_policy_delta" in report
    assert report["head_to_head_rows"][0]["prompt_only_policy_guardrail"]["recommended_action"] in {"accept", "defer"}
    assert (tmp_path / "rows.json").exists()


def test_prompt_policy_decision_blocks_missing_authorization_text():
    module = load_script()
    blocked, route, reasons = module.prompt_policy_decision(
        "Candidate action: get_account_details\nProposed arguments: {}\nConstraints: []\nEvidence summaries: missing authorization."
    )

    assert blocked is True
    assert route == "defer"
    assert "prompt_detected_missing_authorization_text" in reasons


def test_metric_delta_reports_percentage_point_changes():
    module = load_script()
    delta = module.metric_delta(
        {"accuracy_pct": 90.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 80.0},
        {"accuracy_pct": 70.0, "block_recall_pct": 85.0, "safe_allow_rate_pct": 60.0},
    )

    assert delta["accuracy_pct"] == 20.0
    assert delta["block_recall_pct"] == 15.0
    assert delta["safe_allow_rate_pct"] == 20.0
