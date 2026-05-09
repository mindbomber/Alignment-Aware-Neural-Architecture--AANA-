import json
import subprocess
import sys

from fastapi.testclient import TestClient

import aana
from eval_pipeline.fastapi_app import create_app


def test_should_execute_requires_true_accept_across_result_surfaces() -> None:
    result = {
        "gate_decision": "pass",
        "recommended_action": "accept",
        "hard_blockers": [],
        "aix": {"hard_blockers": []},
        "architecture_decision": {"route": "ask", "hard_blockers": []},
    }

    assert not aana.should_execute_tool(result)
    policy = aana.execution_policy(result)
    assert not policy["aana_allows_execution"]
    assert not policy["execution_allowed"]
    assert policy["reason"] == "route_not_accept"


def test_route_table_allows_execution_only_for_accept() -> None:
    for route in ("revise", "retrieve", "ask", "defer", "refuse"):
        result = {
            "gate_decision": "pass",
            "recommended_action": route,
            "hard_blockers": [],
            "aix": {"hard_blockers": []},
            "architecture_decision": {"route": route, "hard_blockers": []},
        }

        assert not aana.should_execute_tool(result)
        policy = aana.execution_policy(result)
        assert not policy["aana_allows_execution"]
        assert not policy["execution_allowed"]
        assert policy["required_route"] == "accept"

    accept = {
        "gate_decision": "pass",
        "recommended_action": "accept",
        "hard_blockers": [],
        "aix": {"hard_blockers": []},
        "architecture_decision": {"route": "accept", "hard_blockers": []},
    }
    assert aana.should_execute_tool(accept)


def test_check_tool_call_fail_closes_malformed_evidence() -> None:
    result = aana.check_tool_call(
        {
            "tool_name": "send_email",
            "tool_category": "write",
            "authorization_state": "confirmed",
            "evidence_refs": [{"source_id": "approval", "kind": "not_a_kind"}],
            "risk_domain": "customer_support",
            "proposed_arguments": {"to": "customer@example.com"},
            "recommended_route": "accept",
        }
    )

    assert result["recommended_action"] == "refuse"
    assert result["gate_decision"] == "fail"
    assert "contract_normalization_failed" in result["hard_blockers"]
    assert not aana.should_execute_tool(result)
    assert result["execution_policy"]["fail_closed"]


def test_optional_semantic_tool_verifier_can_tighten_v2_without_bypassing_aana() -> None:
    event = aana.build_tool_precheck_event(
        tool_name="lookup_policy",
        tool_category="public_read",
        authorization_state="none",
        evidence_refs=["policy:returns"],
        risk_domain="customer_support",
        proposed_arguments={"policy_id": "returns"},
        recommended_route="accept",
    )

    def fake_semantic_verifier(_event, _deterministic_result):
        return {
            "label": "needs_more_evidence",
            "route": "defer",
            "confidence": 0.88,
            "reason_codes": ["missing_policy_scope"],
            "recovery_suggestion": "Retrieve the policy section and recheck.",
        }

    result = aana.check_tool_precheck_v2(event, semantic_verifier=fake_semantic_verifier)

    assert result["recommended_action"] == "defer"
    assert result["gate_decision"] == "fail"
    assert "semantic_tool_use_risk" in result["hard_blockers"]
    assert result["semantic_verifier"]["label"] == "needs_more_evidence"
    assert not aana.should_execute_tool(result)


def test_wrapper_fail_closes_malformed_evidence_without_calling_tool() -> None:
    calls = []

    def send_email(to: str) -> dict:
        calls.append(to)
        return {"sent": True}

    guarded = aana.wrap_agent_tool(
        send_email,
        metadata={
            "tool_category": "write",
            "authorization_state": "confirmed",
            "risk_domain": "customer_support",
            "evidence_refs": [{"source_id": "approval", "kind": "not_a_kind"}],
        },
        raise_on_block=False,
    )

    result = guarded(to="customer@example.com")

    assert calls == []
    assert not result["allowed"]
    assert not result["execution_allowed"]
    assert result["execution_policy"]["fail_closed"]
    assert result["result"]["recommended_action"] == "refuse"


def test_shadow_mode_is_observe_only_and_explicit_for_wrappers() -> None:
    calls = []

    def send_email(to: str) -> dict:
        calls.append(to)
        return {"sent": True}

    guarded = aana.wrap_agent_tool(
        send_email,
        metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
        execution_mode="shadow",
    )

    result = guarded(to="customer@example.com")

    assert result == {"sent": True}
    assert calls == ["customer@example.com"]
    assert not guarded.aana_last_gate["allowed"]
    assert guarded.aana_last_gate["execution_allowed"]
    assert guarded.aana_last_gate["execution_policy"]["mode"] == "shadow"
    assert guarded.aana_last_gate["execution_policy"]["reason"] in {
        "schema_or_contract_validation_failed",
        "route_not_accept",
        "hard_blockers_present",
    }


def test_fastapi_pre_tool_check_shadow_mode_keeps_would_route_visible() -> None:
    client = TestClient(create_app(auth_token=None))

    response = client.post(
        "/pre-tool-check?shadow_mode=true",
        json={
            "tool_name": "send_email",
            "tool_category": "write",
            "authorization_state": "user_claimed",
            "evidence_refs": ["draft_id:123"],
            "risk_domain": "customer_support",
            "proposed_arguments": {"to": "customer@example.com"},
            "recommended_route": "accept",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "shadow"
    assert payload["shadow_observation"]["enforcement"] == "observe_only"
    assert payload["recommended_action"] == "ask"
    assert payload["execution_policy"]["mode"] == "shadow"
    assert not payload["execution_policy"]["aana_allows_execution"]
    assert payload["execution_policy"]["execution_allowed"]


def test_cli_pre_tool_check_exposes_same_execution_policy() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/aana_cli.py",
            "pre-tool-check",
            "--event",
            "examples/agent_tool_precheck_private_read.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["recommended_action"] == "accept"
    assert payload["architecture_decision"]["route"] == "accept"
    assert payload["execution_policy"]["mode"] == "enforce"
    assert payload["execution_policy"]["aana_allows_execution"]
    assert payload["execution_policy"]["execution_allowed"]
