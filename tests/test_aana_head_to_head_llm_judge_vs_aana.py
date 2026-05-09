import importlib.util
import pathlib

from test_aana_external_agent_trace_noisy_evidence_eval import fixture_rows


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "aana_head_to_head_llm_judge_vs_aana.py"
    spec = importlib.util.spec_from_file_location("aana_head_to_head_llm_judge_vs_aana", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_llm_judge_runner_compares_model_judge_to_aana(tmp_path, monkeypatch):
    module = load_script()
    rows = fixture_rows()
    monkeypatch.setattr(module, "build_external_rows", lambda *_args, **_kwargs: rows)

    def fake_judge(prompt, model, max_output_tokens):
        if "initiate_internal_transfer" in prompt:
            return {"decision": "defer", "confidence": 0.9, "reason": "write missing validation"}
        return {"decision": "accept", "confidence": 0.8, "reason": "read appears allowed"}

    monkeypatch.setattr(module, "call_llm_judge", fake_judge)

    report = module.run(
        tmp_path / "report.json",
        tmp_path / "dataset.json",
        tmp_path / "rows.json",
        tmp_path / "cache.jsonl",
        "fixture",
        "train",
        3,
        57,
        "moderate",
        "fixture-model",
        64,
    )

    assert report["comparison"]["baseline"] == "llm_as_judge_safety_checker_over_flattened_action_evidence_text"
    assert "llm_as_judge_safety_checker_metrics" in report
    assert "aana_schema_gate_metrics" in report
    assert "aana_minus_llm_judge_delta" in report
    assert report["head_to_head_rows"][0]["llm_as_judge_safety_checker"]["recommended_action"] == "accept"
    assert (tmp_path / "cache.jsonl").exists()


def test_parse_judge_json_handles_wrapped_json_and_bad_output():
    module = load_script()

    parsed = module.parse_judge_json('Here: {"decision":"defer","confidence":0.7,"reason":"missing auth"}')
    bad = module.parse_judge_json("not json")

    assert parsed["decision"] == "defer"
    assert parsed["confidence"] == 0.7
    assert bad["decision"] == "defer"


def test_metric_delta_reports_percentage_point_changes():
    module = load_script()
    delta = module.metric_delta(
        {"accuracy_pct": 90.0, "block_recall_pct": 100.0, "safe_allow_rate_pct": 80.0},
        {"accuracy_pct": 70.0, "block_recall_pct": 85.0, "safe_allow_rate_pct": 60.0},
    )

    assert delta["accuracy_pct"] == 20.0
    assert delta["block_recall_pct"] == 15.0
    assert delta["safe_allow_rate_pct"] == 20.0
