"""Audit-safe evidence integrity checks for AANA runtime gates."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any


EVIDENCE_SAFETY_VERSION = "0.1"
DEFAULT_MAX_AGE_HOURS = 24 * 7
TRUST_ORDER = {"unknown": 0, "unverified": 1, "user_claimed": 2, "runtime": 3, "verified": 4}
SAFE_REDACTION_STATUSES = {"public", "redacted"}
SENSITIVE_REDACTION_STATUSES = {"sensitive", "unredacted"}
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_.\-]{8,}"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
]
PII_PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
]
MISSING_MARKERS = (
    "evidence missing",
    "missing evidence",
    "information is missing",
    "record is missing",
    "not available",
    "unavailable",
    "unknown",
    "insufficient",
    "no evidence",
)
CONTRADICTORY_MARKERS = ("contradict", "conflict", "inconsistent", "does not match", "disputes", "opposes")


def _parse_time(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = _dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def _contains(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _add_issue(issues: list[dict[str, Any]], level: str, code: str, path: str, message: str) -> None:
    issues.append({"level": level, "code": code, "path": path, "message": message})


def analyze_tool_evidence_refs(
    evidence_refs: list[dict[str, Any]] | None,
    *,
    tool_category: str = "unknown",
    now: _dt.datetime | None = None,
    max_age_hours: int | None = DEFAULT_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Analyze evidence refs for leakage, integrity, freshness, and coverage."""

    refs = evidence_refs or []
    current_time = now or _dt.datetime.now(_dt.timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=_dt.timezone.utc)
    issues: list[dict[str, Any]] = []
    used: list[str] = []
    missing: list[str] = []
    contradictory: list[str] = []
    citations: list[str] = []
    provenance_refs: list[str] = []

    if tool_category in {"private_read", "write", "unknown"} and not refs:
        _add_issue(issues, "error", "missing_evidence_refs", "$.evidence_refs", "Consequential tool call is missing evidence refs.")

    for index, ref in enumerate(refs):
        path = f"$.evidence_refs[{index}]"
        if not isinstance(ref, dict):
            _add_issue(issues, "error", "malformed_evidence_ref", path, "Evidence ref must be an object.")
            continue
        source_id = str(ref.get("source_id") or "")
        summary = str(ref.get("summary") or "")
        text_for_scan = " ".join(str(ref.get(key) or "") for key in ("source_id", "summary", "citation_url", "retrieval_url"))
        if source_id:
            used.append(source_id)
        else:
            _add_issue(issues, "error", "missing_source_id", f"{path}.source_id", "Evidence ref is missing source_id.")

        trust_tier = str(ref.get("trust_tier") or "unknown")
        if trust_tier not in TRUST_ORDER:
            _add_issue(issues, "error", "invalid_trust_tier", f"{path}.trust_tier", "Evidence ref has an unsupported trust tier.")
        elif trust_tier in {"unknown", "unverified"} and tool_category in {"private_read", "write"}:
            _add_issue(issues, "warning", "weak_trust_tier", f"{path}.trust_tier", "Private reads and writes should use runtime or verified evidence.")

        redaction_status = str(ref.get("redaction_status") or "unknown")
        if redaction_status in SENSITIVE_REDACTION_STATUSES:
            _add_issue(issues, "error", "unsafe_redaction_status", f"{path}.redaction_status", "Evidence ref is sensitive or unredacted.")
        elif redaction_status not in SAFE_REDACTION_STATUSES and tool_category in {"private_read", "write"}:
            _add_issue(issues, "warning", "unknown_redaction_status", f"{path}.redaction_status", "Private reads and writes should use public or redacted evidence refs.")

        if _contains(SECRET_PATTERNS, text_for_scan):
            _add_issue(issues, "error", "evidence_secret_leak", path, "Evidence ref appears to contain a raw secret or highly sensitive identifier.")
        elif redaction_status != "redacted" and _contains(PII_PATTERNS, text_for_scan):
            _add_issue(issues, "error", "evidence_pii_leak", path, "Evidence ref appears to contain raw PII without redaction.")

        retrieved_at = ref.get("retrieved_at")
        if retrieved_at:
            parsed = _parse_time(retrieved_at)
            if parsed is None:
                _add_issue(issues, "error", "invalid_retrieved_at", f"{path}.retrieved_at", "retrieved_at must be an ISO timestamp.")
            elif max_age_hours is not None and current_time - parsed > _dt.timedelta(hours=max_age_hours):
                _add_issue(issues, "error", "stale_evidence", f"{path}.retrieved_at", "Evidence ref is stale.")
        elif tool_category in {"private_read", "write"}:
            _add_issue(issues, "warning", "missing_freshness_timestamp", f"{path}.retrieved_at", "Private reads and writes should include retrieved_at.")

        has_provenance = any(ref.get(key) for key in ("citation_url", "retrieval_url", "provenance"))
        if has_provenance:
            provenance_refs.append(source_id or f"evidence_ref:{index + 1}")
        elif tool_category in {"private_read", "write"}:
            _add_issue(issues, "warning", "missing_provenance", path, "Private reads and writes should include citation_url, retrieval_url, or provenance.")

        lower_summary = summary.lower()
        if any(marker in lower_summary for marker in MISSING_MARKERS):
            missing.append(source_id or f"evidence_ref:{index + 1}")
        if ref.get("contradicts") or any(marker in lower_summary for marker in CONTRADICTORY_MARKERS):
            contradictory.append(source_id or f"evidence_ref:{index + 1}")
        if ref.get("citation_url"):
            citations.append(source_id or f"evidence_ref:{index + 1}")

    error_codes = [issue["code"] for issue in issues if issue["level"] == "error"]
    warning_codes = [issue["code"] for issue in issues if issue["level"] == "warning"]
    return {
        "evidence_safety_version": EVIDENCE_SAFETY_VERSION,
        "checked_ref_count": len(refs),
        "used_source_ids": list(dict.fromkeys(used)),
        "missing_evidence_source_ids": list(dict.fromkeys(missing)),
        "contradictory_evidence_source_ids": list(dict.fromkeys(contradictory)),
        "citation_source_ids": list(dict.fromkeys(citations)),
        "provenance_source_ids": list(dict.fromkeys(provenance_refs)),
        "issues": issues,
        "error_codes": list(dict.fromkeys(error_codes)),
        "warning_codes": list(dict.fromkeys(warning_codes)),
        "has_errors": bool(error_codes),
        "has_warnings": bool(warning_codes),
    }


def grounded_qa_evidence_coverage(answer: str, evidence_items: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return citation/evidence coverage for grounded QA outputs."""

    from eval_pipeline.adapter_runner.verifier_modules.grounded_qa import citation_tokens

    answer_citations = sorted(citation_tokens(answer or ""))
    evidence_items = evidence_items or []
    available_citations = []
    support_ids = []
    for index, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or f"evidence:{index + 1}")
        support_ids.append(source_id)
        if item.get("citation_url") or item.get("retrieval_url"):
            available_citations.append(source_id)
    missing_citation_coverage = [token for token in answer_citations if token.strip("[]") not in support_ids and token not in support_ids]
    return {
        "answer_citations": answer_citations,
        "available_citation_source_ids": sorted(set(available_citations)),
        "support_source_ids": sorted(set(support_ids)),
        "missing_citation_coverage": missing_citation_coverage,
        "citation_evidence_coverage": 1.0 if answer_citations and not missing_citation_coverage else 0.0 if answer_citations else 1.0,
    }
