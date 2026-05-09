import importlib.util
import pathlib

from test_aana_external_agent_trace_noisy_evidence_eval import fixture_rows


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "aana_head_to_head_single_classifier_vs_aana.py"
    spec = importlib.util.spec_from_file_location("aana_head_to_head_single_classifier_vs_aana", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_head_to_head_runner_compares_single_classifier_to_aana(tmp_path, monkeypatch):
    module = load_script()
    rows = fixture_rows()
    classifier_scored = [
        {
            **rows[0],
            "blocked": False,
            "correct": True,
            "route_correct": True,
            "recommended_action": "accept",
            "candidate_aix_hard_blockers": [],
            "action_taxonomy_model": {"blocked_probability": 0.1, "threshold": 0.5},
        },
        {
            **rows[1],
            "blocked": False,
            "correct": False,
            "route_correct": False,
            "recommended_action": "accept",
            "candidate_aix_hard_blockers": [],
            "action_taxonomy_model": {"blocked_probability": 0.4, "threshold": 0.5},
        },
        {
            **rows[2],
            "blocked": False,
            "correct": True,
            "route_correct": True,
            "recommended_action": "accept",
            "candidate_aix_hard_blockers": [],
            "action_taxonomy_model": {"blocked_probability": 0.1, "threshold": 0.5},
        },
    ]
    monkeypatch.setattr(module, "build_external_rows", lambda *_args, **_kwargs: rows)
    monkeypatch.setattr(module, "score_single_classifier_rows", lambda *_args, **_kwargs: {"scored": classifier_scored, "threshold": 0.5})

    report = module.run(
        tmp_path / "report.json",
        tmp_path / "dataset.json",
        tmp_path / "rows.json",
        "fixture",
        "train",
        3,
        57,
        "moderate",
        tmp_path / "model.joblib",
    )

    assert report["comparison"]["baseline"] == "single_tfidf_logistic_regression_action_classifier_trained_on_blind_v3_v4"
    assert report["single_classifier_metrics"]["fn"] == 1
    assert "aana_schema_gate_metrics" in report
    assert "aana_minus_single_classifier_delta" in report
    assert report["head_to_head_rows"][0]["single_classifier"]["recommended_action"] == "accept"
    assert (tmp_path / "rows.json").exists()


def test_metric_delta_reports_percentage_point_changes():
    module = load_script()
    delta = module.metric_delta(
        {"accuracy_pct": 90.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 80.0},
        {"accuracy_pct": 60.0, "block_recall_pct": 40.0, "safe_allow_rate_pct": 95.0},
    )

    assert delta["accuracy_pct"] == 30.0
    assert delta["block_recall_pct"] == 60.0
    assert delta["safe_allow_rate_pct"] == -15.0
