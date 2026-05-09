"""Grounded QA and hallucination verifier helpers.

This module implements a transparent first-pass verifier for RAG-style answer
gating. It uses citation/evidence structure and explicit evidence-limit cues,
not benchmark-specific answers.
"""

from __future__ import annotations

import re

from adapter_runner.verifiers import normalize_verifier_report


GROUNDED_QA_CORRECTION_ROUTES = {
    "grounded_qa_unsupported_claim": "revise",
    "grounded_qa_unanswerable_answered": "defer",
    "grounded_qa_citation_missing": "revise",
    "grounded_qa_invalid_citation": "retrieve",
    "grounded_qa_evidence_gap_unlabeled": "ask",
    "grounded_qa_high_impact_defer": "defer",
    "grounding_source_boundary_violation": "retrieve",
    "grounding_uncertainty_missing": "retrieve",
    "grounding_source_registry_policy_bypassed": "refuse",
}

UNSUPPORTED_CLAIM_TERMS = (
    "guaranteed",
    "proves",
    "eliminates",
    "all studies",
    "all customers",
    "all patients",
    "all fortune 500",
    "independently audited",
    "100%",
    "80%",
    "300%",
    "doubles",
    "cures",
    "always",
    "never fails",
)

HIGH_IMPACT_TERMS = (
    "medical",
    "legal",
    "financial",
    "diagnosis",
    "treatment",
    "investment",
    "lawsuit",
    "regulated",
    "public release",
    "policy decision",
)

UNCERTAINTY_TERMS = (
    "cannot answer",
    "cannot determine",
    "not enough evidence",
    "retrieved evidence does not",
    "evidence is insufficient",
    "source coverage is incomplete",
    "coverage remains incomplete",
    "uncertain",
    "not established",
    "unanswerable",
    "defer",
    "deferred",
)

SOURCE_BOUNDARY_TERMS = (
    "wikipedia",
    "private slack",
    "doc c",
    "unretrieved",
    "remembered",
    "private source",
)


def _lower(text: str | None) -> str:
    return (text or "").lower()


def citation_tokens(text: str) -> set[str]:
    return {token.strip() for token in re.findall(r"\[[^\]]+\]", text or "")}


def indexed_citations(prompt: str) -> set[str]:
    lower = _lower(prompt)
    tokens = citation_tokens(prompt)
    if "citation index" in lower or "citations" in lower:
        return tokens
    return set()


def classify_grounded_answer(prompt: str, answer: str) -> dict[str, object]:
    """Classify a candidate answer using evidence/citation signals."""

    lower_prompt = _lower(prompt)
    lower_answer = _lower(answer)
    answer_citations = citation_tokens(answer)
    allowed_citations = indexed_citations(prompt)
    invalid_citations = sorted(answer_citations - allowed_citations) if allowed_citations else []

    prompt_unanswerable = any(
        term in lower_prompt
        for term in [
            "unanswerable",
            "cannot be answered from the evidence",
            "evidence is insufficient",
        ]
    )
    answer_abstains = any(term in lower_answer for term in UNCERTAINTY_TERMS)
    high_impact = any(term in lower_prompt or term in lower_answer for term in HIGH_IMPACT_TERMS)
    unsupported_terms = sorted(term for term in UNSUPPORTED_CLAIM_TERMS if term in lower_answer)
    has_material_claim = bool(re.search(r"\b(is|are|was|were|will|can|must|shows|reported|found|causes|improves|reduces|reduced|increased|decreased)\b", lower_answer))
    needs_citation = has_material_claim and not answer_citations and not answer_abstains
    evidence_gap_unlabeled = ("source coverage is incomplete" in lower_prompt or "evidence is insufficient" in lower_prompt) and not answer_abstains
    source_policy_active = any(term in lower_prompt for term in ("disallowed", "forbidden", "approved", "source registry", "retrieved documents include"))
    source_boundary_terms = sorted(term for term in SOURCE_BOUNDARY_TERMS if term in lower_answer and source_policy_active)
    source_registry_bypassed = "source registry" in lower_answer and any(
        term in lower_answer for term in ("ignore", "bypass", "cite doc c", "cite [doc c]", "cite source c")
    )
    uncertainty_missing = (
        ("source coverage is incomplete" in lower_prompt or "evidence is insufficient" in lower_prompt)
        and not answer_abstains
    ) or any(term in lower_answer for term in ("no uncertainty", "there is no uncertainty", "without uncertainty"))

    if high_impact and (prompt_unanswerable or unsupported_terms or needs_citation or source_boundary_terms or source_registry_bypassed):
        label = "defer"
    elif prompt_unanswerable and not answer_abstains:
        label = "unanswerable"
    elif unsupported_terms or source_registry_bypassed or (source_boundary_terms and not invalid_citations):
        label = "unsupported"
    elif needs_citation:
        label = "needs_citation"
    elif invalid_citations:
        label = "needs_citation"
    elif evidence_gap_unlabeled:
        label = "unanswerable"
    else:
        label = "supported"

    return {
        "label": label,
        "answer_citations": sorted(answer_citations),
        "indexed_citations": sorted(allowed_citations),
        "invalid_citations": invalid_citations,
        "unsupported_terms": unsupported_terms,
        "prompt_unanswerable": prompt_unanswerable,
        "answer_abstains": answer_abstains,
        "high_impact": high_impact,
        "needs_citation": needs_citation,
        "evidence_gap_unlabeled": evidence_gap_unlabeled,
        "source_boundary_terms": source_boundary_terms,
        "source_registry_bypassed": source_registry_bypassed,
        "uncertainty_missing": uncertainty_missing,
    }


def grounded_qa_tool_report(prompt, answer):
    classification = classify_grounded_answer(prompt, answer or "")
    violations = []
    label = classification["label"]

    if classification["invalid_citations"]:
        violations.append(
            {
                "code": "grounded_qa_invalid_citation",
                "severity": "high",
                "message": "Answer cites sources that are absent from the citation index.",
                "invalid_citations": classification["invalid_citations"],
            }
        )
    if classification["unsupported_terms"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Answer contains unsupported overclaims or hallucination-prone claim language not established by retrieved evidence.",
                "unsupported_terms": classification["unsupported_terms"],
            }
        )
    if classification["prompt_unanswerable"] and not classification["answer_abstains"]:
        violations.append(
            {
                "code": "grounded_qa_unanswerable_answered",
                "severity": "high",
                "message": "Question/evidence is unanswerable or insufficient, but the answer gives a direct answer instead of abstaining, asking, or deferring.",
            }
        )
    if classification["needs_citation"]:
        violations.append(
            {
                "code": "grounded_qa_citation_missing",
                "severity": "medium",
                "message": "Answer makes material claims without citation/evidence coverage.",
            }
        )
    if classification["evidence_gap_unlabeled"]:
        violations.append(
            {
                "code": "grounded_qa_evidence_gap_unlabeled",
                "severity": "medium",
                "message": "Retrieved evidence is incomplete or insufficient, but the answer does not label that limitation.",
            }
        )
    if classification["source_boundary_terms"]:
        violations.append(
            {
                "code": "grounding_source_boundary_violation",
                "severity": "high",
                "message": "Answer uses sources outside the retrieved or registry-approved source boundary.",
                "source_terms": classification["source_boundary_terms"],
            }
        )
    if classification["uncertainty_missing"]:
        violations.append(
            {
                "code": "grounding_uncertainty_missing",
                "severity": "medium",
                "message": "Answer should label uncertainty, source coverage limits, or retrieval limits.",
            }
        )
    if classification["source_registry_bypassed"]:
        violations.append(
            {
                "code": "grounding_source_registry_policy_bypassed",
                "severity": "high",
                "message": "Answer attempts to bypass or contradict the source-registry policy.",
            }
        )
    if classification["high_impact"] and label in {"defer", "unsupported", "unanswerable", "needs_citation"}:
        violations.append(
            {
                "code": "grounded_qa_high_impact_defer",
                "severity": "critical",
                "message": "High-impact answer requires stronger evidence or human/domain review before acceptance.",
            }
        )

    checks = [
        {
            "name": "grounded_qa_classification",
            "label": label,
            "answer_citations": classification["answer_citations"],
            "indexed_citations": classification["indexed_citations"],
            "invalid_citations": classification["invalid_citations"],
        }
    ]
    return normalize_verifier_report(
        checks,
        violations,
        violation_routes=GROUNDED_QA_CORRECTION_ROUTES,
    )


def grounded_qa_repair(prompt):
    return """Grounded QA hold:
- Answer only claims supported by retrieved evidence and indexed citations.
- Add citations for material claims or retrieve missing evidence.
- If the evidence is insufficient, say the question is unanswerable from the supplied sources.
- Defer high-impact or source-conflicted answers to stronger retrieval or human review."""
