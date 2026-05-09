import json
import pathlib

from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "sdk" / "agent_tool_precheck_examples.json"


def load_examples():
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))["examples"]


def test_public_read_accepts():
    event = load_examples()[0]["event"]
    result = gate_pre_tool_call(event)
    assert result["recommended_action"] == "accept"
    assert result["gate_decision"] == "pass"
    assert result["hard_blockers"] == []


def test_public_read_defers_on_verified_missing_authorization_evidence():
    event = load_examples()[0]["event"] | {
        "evidence_refs": [
            *load_examples()[0]["event"]["evidence_refs"],
            {
                "source_id": "counterfactual.missing_authorization",
                "kind": "system_state",
                "trust_tier": "verified",
                "redaction_status": "public",
                "summary": "Counterfactual stressor removes verified authorization context.",
            },
        ]
    }
    result = gate_pre_tool_call(event)
    assert result["recommended_action"] == "defer"
    assert result["gate_decision"] == "fail"
    assert "evidence_missing_authorization" in result["hard_blockers"]


def test_private_read_accepts_when_authenticated():
    event = load_examples()[1]["event"]
    result = gate_pre_tool_call(event)
    assert result["recommended_action"] == "accept"
    assert result["gate_decision"] == "pass"


def test_write_defers_when_runtime_defers():
    event = load_examples()[2]["event"]
    result = gate_pre_tool_call(event)
    assert result["recommended_action"] == "defer"
    assert result["gate_decision"] == "fail"
    assert "write_missing_validation_or_confirmation" in result["hard_blockers"]


def test_private_read_without_auth_asks_or_defers():
    event = load_examples()[1]["event"] | {
        "authorization_state": "user_claimed",
        "recommended_route": "ask",
    }
    result = gate_pre_tool_call(event)
    assert result["recommended_action"] == "ask"
    assert result["gate_decision"] == "fail"
    assert "private_read_not_authenticated" in result["hard_blockers"]


def test_invalid_event_refuses():
    result = gate_pre_tool_call({"tool_name": "x"})
    assert result["recommended_action"] == "refuse"
    assert result["gate_decision"] == "fail"
    assert "schema_validation_failed" in result["hard_blockers"]


def test_agent_action_contract_v1_accepts_public_seven_field_minimum():
    event = {
        "tool_name": "get_game_score",
        "tool_category": "public_read",
        "authorization_state": "none",
        "evidence_refs": [
            {
                "source_id": "policy.public_scores",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "public",
            }
        ],
        "risk_domain": "public_information",
        "proposed_arguments": {"game_id": "GAME-123"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert result["contract_version"] == "aana.agent_tool_precheck.v1"
    assert result["recommended_action"] == "accept"
    assert result["gate_decision"] == "pass"


def test_agent_action_contract_v1_still_accepts_schema_version_compatibility_marker():
    event = {
        "schema_version": "aana.agent_tool_precheck.v1",
        "tool_name": "get_game_score",
        "tool_category": "public_read",
        "authorization_state": "none",
        "evidence_refs": [
            {
                "source_id": "policy.public_scores",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "public",
            }
        ],
        "risk_domain": "public_information",
        "proposed_arguments": {"game_id": "GAME-123"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert result["recommended_action"] == "accept"
    assert result["gate_decision"] == "pass"
