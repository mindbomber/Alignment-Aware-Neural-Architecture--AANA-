import aana
from eval_pipeline.pre_tool_call_gate import (
    authorization_state_from_evidence,
    gate_pre_tool_call,
    is_high_risk_write,
    is_identity_bound_read,
)


def test_authorization_state_detection_levels() -> None:
    event = {
        "authorization_state": "none",
        "evidence_refs": [
            {"source_id": "msg.claim", "kind": "user_message", "trust_tier": "user_claimed", "redaction_status": "redacted"},
            {"source_id": "auth.login", "kind": "auth_event", "trust_tier": "verified", "redaction_status": "redacted"},
            {"source_id": "tool.validation", "kind": "tool_result", "trust_tier": "verified", "redaction_status": "redacted", "summary": "Ownership validated."},
            {"source_id": "approval.final", "kind": "approval", "trust_tier": "verified", "redaction_status": "redacted", "summary": "User explicitly confirmed."},
        ],
    }

    report = authorization_state_from_evidence(event)

    assert report["declared_state"] == "none"
    assert report["evidence_supported_state"] == "confirmed"
    assert report["effective_state"] == "confirmed"
    assert report["support"] == ["user_claimed", "authenticated", "validated", "confirmed"]


def test_public_read_with_identity_bound_arguments_is_reclassified_private() -> None:
    event = {
        "tool_name": "get_public_status",
        "tool_category": "public_read",
        "authorization_state": "none",
        "evidence_refs": [
            {
                "source_id": "policy.public_status",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "public",
                "summary": "Public service status is public.",
            }
        ],
        "risk_domain": "finance",
        "proposed_arguments": {"account_id": "acct_redacted"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert is_identity_bound_read(event)
    assert result["recommended_action"] == "defer"
    assert "public_read_identity_bound_misclassified" in result["hard_blockers"]
    assert "private_read_not_authenticated" in result["hard_blockers"]


def test_private_read_authenticated_by_auth_event_accepts() -> None:
    event = {
        "tool_name": "get_customer_profile",
        "tool_category": "private_read",
        "authorization_state": "none",
        "evidence_refs": [
            {"source_id": "auth.session", "kind": "auth_event", "trust_tier": "verified", "redaction_status": "redacted"},
        ],
        "risk_domain": "customer_support",
        "proposed_arguments": {"customer_id": "customer_redacted"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert result["recommended_action"] == "accept"
    assert result["authorization_report"]["effective_state"] == "authenticated"


def test_high_risk_write_requires_confirmation_not_just_validation() -> None:
    event = {
        "tool_name": "transfer_funds",
        "tool_category": "write",
        "authorization_state": "validated",
        "evidence_refs": [
            {"source_id": "auth.session", "kind": "auth_event", "trust_tier": "verified", "redaction_status": "redacted"},
            {"source_id": "tool.validation", "kind": "tool_result", "trust_tier": "verified", "redaction_status": "redacted", "summary": "Account ownership validated."},
        ],
        "risk_domain": "finance",
        "proposed_arguments": {"from_account_id": "acct_a", "to_account_id": "acct_b", "amount": "redacted"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert is_high_risk_write(event)
    assert result["recommended_action"] == "ask"
    assert "high_risk_write_missing_explicit_confirmation" in result["hard_blockers"]


def test_high_risk_write_accepts_with_explicit_confirmation_evidence() -> None:
    event = {
        "tool_name": "transfer_funds",
        "tool_category": "write",
        "authorization_state": "confirmed",
        "evidence_refs": [
            {"source_id": "auth.session", "kind": "auth_event", "trust_tier": "verified", "redaction_status": "redacted"},
            {"source_id": "tool.validation", "kind": "tool_result", "trust_tier": "verified", "redaction_status": "redacted", "summary": "Account ownership validated."},
            {"source_id": "approval.final", "kind": "approval", "trust_tier": "verified", "redaction_status": "redacted", "summary": "User explicitly confirmed transfer."},
        ],
        "risk_domain": "finance",
        "proposed_arguments": {"from_account_id": "acct_a", "to_account_id": "acct_b", "amount": "redacted"},
        "recommended_route": "accept",
    }

    result = aana.check_tool_call(event)

    assert result["recommended_action"] == "accept"
    assert result["architecture_decision"]["authorization_report"]["effective_state"] == "confirmed"
    assert aana.should_execute_tool(result)


def test_ambiguous_declared_confirmed_without_supporting_evidence_downgrades() -> None:
    event = {
        "tool_name": "delete_customer_account",
        "tool_category": "write",
        "authorization_state": "confirmed",
        "evidence_refs": [
            {
                "source_id": "policy.account_deletion",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "public",
                "summary": "Deletion policy exists, but this record is not an approval.",
            }
        ],
        "risk_domain": "customer_support",
        "proposed_arguments": {"customer_id": "customer_redacted"},
        "recommended_route": "accept",
    }

    result = gate_pre_tool_call(event)

    assert result["authorization_report"]["downgraded"]
    assert result["recommended_action"] == "ask"
    assert "authorization_state_not_supported_by_evidence" in result["hard_blockers"]
