import importlib.util
import pathlib

from test_aana_external_agent_trace_noisy_evidence_eval import fixture_rows


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "evals" / "aana_head_to_head_contract_no_recovery_vs_aana.py"
    spec = importlib.util.spec_from_file_location("aana_head_to_head_contract_no_recovery_vs_aana", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recovery_runner_compares_bare_contract_to_aana(tmp_path, monkeypatch):
    module = load_script()
    monkeypatch.setattr(module, "build_external_rows", lambda *_args, **_kwargs: fixture_rows())

    report = module.run(
        tmp_path / "report.json",
        tmp_path / "dataset.json",
        tmp_path / "rows.json",
        tmp_path / "events.json",
        "fixture",
        "train",
        3,
        57,
        "moderate",
    )

    assert report["comparison"]["baseline"] == "structured_contract_gate_without_correction_or_evidence_recovery"
    assert "structured_contract_gate_without_recovery_metrics" in report
    assert "aana_with_evidence_recovery_metrics" in report
    assert "aana_minus_bare_contract_delta" in report
    assert (tmp_path / "events.json").exists()


def test_recovery_removes_noisy_missing_auth_without_using_label():
    module = load_script()
    row = fixture_rows()[2]
    event = {
        "tool_category": "public_read",
        "authorization_state": "none",
        "recommended_route": "accept",
        "evidence_refs": [
            {
                "source_id": "counterfactual.missing_authorization.noisy_trace",
                "kind": "system_state",
                "trust_tier": "verified",
                "summary": "Noisy external trace evidence declares missing authorization.",
            }
        ],
    }

    recovered, actions = module.recover_contract_event(event, row)

    assert not recovered["evidence_refs"]
    assert "removed_noisy_missing_authorization_ref" in actions


def test_metric_delta_reports_percentage_point_changes():
    module = load_script()
    delta = module.metric_delta(
        {"accuracy_pct": 100.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 95.0},
        {"accuracy_pct": 90.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 80.0},
    )

    assert delta["accuracy_pct"] == 10.0
    assert delta["block_recall_pct"] == 0.0
    assert delta["safe_allow_rate_pct"] == 15.0
