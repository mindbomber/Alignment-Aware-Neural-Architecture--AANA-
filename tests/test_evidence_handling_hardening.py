import datetime as dt

import aana
from eval_pipeline.evidence_safety import analyze_tool_evidence_refs, grounded_qa_evidence_coverage


def test_evidence_refs_do_not_return_raw_secret_values() -> None:
    report = analyze_tool_evidence_refs(
        [
            aana.tool_evidence_ref(
                source_id="runtime.secret",
                kind="system_state",
                trust_tier="runtime",
                redaction_status="public",
                summary="api_key=sk-test1234567890abcdef should not be here",
            )
        ],
        tool_category="write",
    )

    assert "evidence_secret_leak" in report["error_codes"]
    assert "sk-test" not in str(report)


def test_tool_gate_refuses_secret_or_pii_evidence_leaks() -> None:
    result = aana.check_tool_call(
        {
            "tool_name": "send_email",
            "tool_category": "write",
            "authorization_state": "confirmed",
            "evidence_refs": [
                {
                    "source_id": "approval.secret",
                    "kind": "approval",
                    "trust_tier": "verified",
                    "redaction_status": "public",
                    "summary": "token=sk-test1234567890abcdef",
                }
            ],
            "risk_domain": "customer_support",
            "proposed_arguments": {"to": "customer@example.com"},
            "recommended_route": "accept",
        }
    )

    assert result["recommended_action"] == "refuse"
    assert "evidence_secret_leak" in result["hard_blockers"]
    assert not aana.should_execute_tool(result)


def test_evidence_integrity_checks_freshness_and_provenance() -> None:
    now = dt.datetime(2026, 5, 9, tzinfo=dt.timezone.utc)
    report = analyze_tool_evidence_refs(
        [
            {
                "source_id": "auth.old",
                "kind": "auth_event",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "retrieved_at": "2026-04-01T00:00:00Z",
                "retrieval_url": "aana://auth/old",
            }
        ],
        tool_category="private_read",
        now=now,
        max_age_hours=24,
    )

    assert "stale_evidence" in report["error_codes"]
    assert report["provenance_source_ids"] == ["auth.old"]


def test_missing_and_contradictory_evidence_are_distinct() -> None:
    result = aana.check_tool_call(
        {
            "tool_name": "send_refund",
            "tool_category": "write",
            "authorization_state": "confirmed",
            "evidence_refs": [
                {
                    "source_id": "policy.missing",
                    "kind": "policy",
                    "trust_tier": "verified",
                    "redaction_status": "public",
                    "summary": "Refund eligibility information is missing from available records.",
                },
                {
                    "source_id": "order.conflict",
                    "kind": "tool_result",
                    "trust_tier": "verified",
                    "redaction_status": "redacted",
                    "summary": "Order record contradicts the requested refund action.",
                    "contradicts": ["refund_allowed"],
                },
            ],
            "risk_domain": "commerce",
            "proposed_arguments": {"order_id": "order_redacted"},
            "recommended_route": "accept",
        }
    )

    decision_refs = result["architecture_decision"]["evidence_refs"]
    assert result["recommended_action"] == "defer"
    assert "evidence_marks_missing_information" in result["hard_blockers"]
    assert "contradictory_evidence" in result["hard_blockers"]
    assert "evidence_marks_missing_information" in decision_refs["missing"]
    assert decision_refs["contradictory"] == ["order.conflict", "contradictory_evidence"]


def test_grounded_qa_citation_evidence_coverage_helper() -> None:
    coverage = grounded_qa_evidence_coverage(
        "AANA checks actions before execution [doc-a]. Unsupported citation [doc-c].",
        [
            {
                "source_id": "doc-a",
                "text": "AANA checks actions before execution.",
                "citation_url": "https://example.test/doc-a",
            }
        ],
    )

    assert coverage["citation_evidence_coverage"] == 0.0
    assert coverage["missing_citation_coverage"] == ["[doc-c]"]
