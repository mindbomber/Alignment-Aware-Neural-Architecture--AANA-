import importlib.util
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_trajectory(tmp_path):
    trajectory_dir = tmp_path / "trajectories"
    trajectory_dir.mkdir()
    payload = {
        "info": {"environment_info": {"domain_name": "retail"}},
        "simulations": [
            {
                "id": "sim-success",
                "task_id": "task-success",
                "trial": 0,
                "termination_reason": "user_stop",
                "reward_info": {
                    "reward": 1.0,
                    "action_checks": [
                        {
                            "action": {"name": "return_delivered_order_items", "arguments": {"order_id": "order_1"}},
                            "action_match": True,
                            "action_reward": 1.0,
                            "tool_type": "write",
                        }
                    ],
                },
                "messages": [
                    {"role": "user", "content": "Yes, return the delivered item.", "turn_idx": 1},
                    {
                        "role": "assistant",
                        "turn_idx": 2,
                        "tool_calls": [{"name": "return_delivered_order_items", "arguments": {"order_id": "order_1"}}],
                        "raw_data": {
                            "aana_gate_records": [
                                {
                                    "tool_name": "return_delivered_order_items",
                                    "tool_category": "write",
                                    "authorization_state": "confirmed",
                                    "risk_domain": "commerce",
                                    "recommended_action": "accept",
                                    "gate_decision": "pass",
                                    "hard_blockers": [],
                                }
                            ]
                        },
                    },
                ],
            },
            {
                "id": "sim-fail",
                "task_id": "task-fail",
                "trial": 0,
                "termination_reason": "user_stop",
                "reward_info": {"reward": 0.0, "action_checks": []},
                "messages": [
                    {"role": "user", "content": "Calculate the refund.", "turn_idx": 1},
                    {
                        "role": "assistant",
                        "turn_idx": 2,
                        "tool_calls": [{"name": "calculate", "arguments": {"expression": "2+2"}}],
                        "raw_data": {
                            "aana_gate_records": [
                                {
                                    "tool_name": "calculate",
                                    "recommended_action": "refuse",
                                    "gate_decision": "fail",
                                    "hard_blockers": ["schema_validation_failed"],
                                    "validation_errors": [{"path": "recommended_route", "message": "accept is invalid for unknown"}],
                                }
                            ]
                        },
                    },
                ],
            },
        ],
    }
    (trajectory_dir / "retail_results.json").write_text(json.dumps(payload), encoding="utf-8")
    return trajectory_dir


def test_tau2_extractor_creates_labeled_rows(tmp_path):
    module = load_script("aana_tau2_tool_call_v2_extract")
    output = tmp_path / "dataset.json"

    report = module.run(fixture_trajectory(tmp_path), output)
    rows = json.loads(output.read_text(encoding="utf-8"))

    assert report["rows"] == 2
    assert report["domain_counts"]["retail"] == 2
    assert {row["label"] for row in rows} == {"should_execute", "should_block_or_ask"}
    assert rows[1]["v1_validation_errors"]


def test_tau2_trainer_writes_model_report_and_scored_outputs(tmp_path):
    train = load_script("aana_tau2_action_taxonomy_v2_train")
    rows = []
    for index in range(16):
        rows.append(
            {
                "id": f"execute-{index}",
                "domain": "retail",
                "tool_name": "return_delivered_order_items",
                "tool_arguments": {"order_id": f"order_{index}"},
                "latest_user_message": "Yes, please return the delivered item.",
                "label": "should_execute",
                "label_source": "matched_positive_action_check",
                "v1_gate_result": {"tool_category": "write", "authorization_state": "confirmed", "risk_domain": "commerce", "recommended_action": "accept", "hard_blockers": []},
            }
        )
        rows.append(
            {
                "id": f"block-{index}",
                "domain": "retail",
                "tool_name": "calculate",
                "tool_arguments": {"expression": "2+2"},
                "latest_user_message": "Calculate the refund.",
                "label": "should_block_or_ask",
                "label_source": "v1_schema_validation_failure",
                "v1_gate_result": {"tool_category": "unknown", "authorization_state": "none", "risk_domain": "commerce", "recommended_action": "refuse", "hard_blockers": ["schema_validation_failed"]},
            }
        )
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps(rows), encoding="utf-8")

    report = train.run(
        dataset,
        tmp_path / "report.json",
        tmp_path / "scored.json",
        tmp_path / "model.joblib",
        0.75,
        0.75,
    )

    assert report["rows_trainable"] == 32
    assert report["excluded_review_or_holdout"] == 0
    assert (tmp_path / "model.joblib").exists()
    assert (tmp_path / "scored.json").exists()
