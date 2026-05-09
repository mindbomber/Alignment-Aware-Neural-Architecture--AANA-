import aana
from eval_pipeline.authorization_state import (
    AUTHORIZATION_STATES,
    AUTHORIZATION_STATE_TABLE,
    auth_state_at_least,
    authorization_transition_report,
    canonicalize_authorization_state,
    private_read_allowed,
    write_execution_allowed,
    write_schema_accept_allowed,
)
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call


def _ref(source_id: str, kind: str, summary: str = "") -> dict:
    return aana.tool_evidence_ref(
        source_id=source_id,
        kind=kind,
        trust_tier="verified" if kind != "user_message" else "user_claimed",
        redaction_status="redacted",
        freshness={"status": "fresh"},
        provenance="test",
        summary=summary,
    )


def _event(category: str, auth_state: str, evidence_refs: list[dict], recommended_route: str = "accept") -> dict:
    return {
        "tool_name": "get_customer_profile" if category == "private_read" else "send_customer_email",
        "tool_category": category,
        "authorization_state": auth_state,
        "evidence_refs": evidence_refs,
        "risk_domain": "customer_support",
        "proposed_arguments": {"customer_id": "customer_redacted"},
        "recommended_route": recommended_route,
    }


def test_authorization_state_order_and_capabilities_are_canonical() -> None:
    assert AUTHORIZATION_STATES == ("none", "user_claimed", "authenticated", "validated", "confirmed")
    assert tuple(AUTHORIZATION_STATE_TABLE) == AUTHORIZATION_STATES
    assert [AUTHORIZATION_STATE_TABLE[state]["rank"] for state in AUTHORIZATION_STATES] == [0, 1, 2, 3, 4]
    assert not private_read_allowed("user_claimed")
    assert private_read_allowed("authenticated")
    assert not write_schema_accept_allowed("authenticated")
    assert write_schema_accept_allowed("validated")
    assert not write_execution_allowed("validated")
    assert write_execution_allowed("confirmed")
    assert auth_state_at_least("confirmed", "validated")


def test_ambiguous_authorization_labels_normalize_fail_closed() -> None:
    assert canonicalize_authorization_state("logged-in") == "authenticated"
    assert canonicalize_authorization_state("maybe_validated") == "none"
    assert canonicalize_authorization_state("ownership_validated") == "validated"
    assert canonicalize_authorization_state("banana") == "none"

    report = authorization_transition_report("logged in")

    assert report["canonical_state"] == "authenticated"
    assert report["ambiguous"]
    assert report["private_read_allowed"]
    assert not report["write_execution_allowed"]
    assert report["needs_confirmation"]


def test_private_read_transitions_require_authenticated_or_stronger() -> None:
    user_claimed = gate_pre_tool_call(
        _event("private_read", "user_claimed", [_ref("msg.request", "user_message", "User requests their profile.")], recommended_route="ask")
    )
    authenticated = gate_pre_tool_call(
        _event("private_read", "authenticated", [_ref("auth.session", "auth_event", "Identity was authenticated.")])
    )

    assert user_claimed["recommended_action"] == "ask"
    assert "private_read_not_authenticated" in user_claimed["hard_blockers"]
    assert authenticated["recommended_action"] == "accept"


def test_write_transitions_require_confirmation_for_execution() -> None:
    validated = gate_pre_tool_call(
        _event(
            "write",
            "validated",
            [
                _ref("auth.session", "auth_event", "Identity was authenticated."),
                _ref("tool.validation", "tool_result", "Recipient and policy validation passed."),
            ],
        )
    )
    confirmed = gate_pre_tool_call(
        _event(
            "write",
            "confirmed",
            [
                _ref("auth.session", "auth_event", "Identity was authenticated."),
                _ref("tool.validation", "tool_result", "Recipient and policy validation passed."),
                _ref("approval.confirmation", "approval", "User explicitly confirmed sending the email."),
            ],
        )
    )

    assert validated["recommended_action"] == "ask"
    assert "write_missing_explicit_confirmation" in validated["hard_blockers"]
    assert confirmed["recommended_action"] == "accept"
