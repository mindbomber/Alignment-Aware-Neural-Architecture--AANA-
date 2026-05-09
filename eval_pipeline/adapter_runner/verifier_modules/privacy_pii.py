"""Privacy/PII verifier and redaction routing helpers.

The detector is intentionally transparent and conservative: it catches common
identifier forms and multilingual label cues, then routes by evidence state
instead of memorizing benchmark examples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from adapter_runner.verifiers import normalize_verifier_report


PRIVACY_PII_CORRECTION_ROUTES = {
    "pii_unredacted": "revise",
    "pii_redaction_missing": "revise",
    "private_identity_detail_exposed": "refuse",
    "pii_authorization_missing": "ask",
    "pii_multilingual_identifier_unredacted": "revise",
}

HIGH_RISK_CATEGORIES = {
    "ssn",
    "credit_card",
    "iban",
    "passport",
    "drivers_license",
    "medical_record",
    "national_id",
}

SAFE_PLACEHOLDERS = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "ssn": "[REDACTED_SSN]",
    "credit_card": "[REDACTED_CARD]",
    "iban": "[REDACTED_IBAN]",
    "ip_address": "[REDACTED_IP]",
    "date_of_birth": "[REDACTED_DOB]",
    "street_address": "[REDACTED_ADDRESS]",
    "passport": "[REDACTED_PASSPORT]",
    "drivers_license": "[REDACTED_DRIVER_LICENSE]",
    "medical_record": "[REDACTED_MEDICAL_RECORD]",
    "national_id": "[REDACTED_NATIONAL_ID]",
}

PUBLIC_CONTEXT_TERMS = {
    "public contact",
    "press contact",
    "support inbox",
    "company support",
    "business contact",
    "public helpdesk",
}


@dataclass(frozen=True)
class PiiPattern:
    category: str
    pattern: re.Pattern
    label_sensitive: bool = False


PII_PATTERNS = (
    PiiPattern("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    PiiPattern("ssn", re.compile(r"\b(?:SSN|NSS|social security|numero de seguro social)[:\s#-]*\d{3}[- ]?\d{2}[- ]?\d{4}\b", re.I)),
    PiiPattern("ssn", re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")),
    PiiPattern("credit_card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    PiiPattern("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.I)),
    PiiPattern("phone", re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")),
    PiiPattern("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    PiiPattern("date_of_birth", re.compile(r"\b(?:DOB|date of birth|fecha de nacimiento|date de naissance|geburtsdatum)[:\s-]*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", re.I)),
    PiiPattern("street_address", re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.' -]{2,40}\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|calle|rue)\b", re.I)),
    PiiPattern("passport", re.compile(r"\b(?:passport|pasaporte|passeport)[:\s#-]*[A-Z0-9]{6,12}\b", re.I)),
    PiiPattern("drivers_license", re.compile(r"\b(?:driver'?s license|licencia de conducir|permis de conduire)[:\s#-]*[A-Z0-9-]{5,18}\b", re.I)),
    PiiPattern("medical_record", re.compile(r"\b(?:MRN|medical record|numero de historia clinica)[:\s#-]*[A-Z0-9-]{5,18}\b", re.I)),
    PiiPattern("national_id", re.compile(r"\b(?:DNI|NIF|national id|numero nacional|identifiant national)[:\s#-]*[A-Z0-9-]{5,18}\b", re.I)),
)


def _valid_ip(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def _digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _luhn_valid(value: str) -> bool:
    digits = [int(char) for char in _digits(value)]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _is_public_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 80) : min(len(text), end + 80)].lower()
    return any(term in window for term in PUBLIC_CONTEXT_TERMS)


def _should_keep_match(category: str, value: str, text: str, start: int, end: int) -> bool:
    if category == "credit_card" and not _luhn_valid(value):
        return False
    if category == "ip_address" and not _valid_ip(value):
        return False
    if category == "email" and _is_public_context(text, start, end):
        return False
    if category == "phone" and _is_public_context(text, start, end):
        return False
    return True


def detect_pii(text: str) -> list[dict[str, object]]:
    """Return non-overlapping PII spans with category and replacement text."""

    text = text or ""
    matches: list[dict[str, object]] = []
    occupied: list[tuple[int, int]] = []
    for spec in PII_PATTERNS:
        for match in spec.pattern.finditer(text):
            start, end = match.span()
            value = match.group(0)
            if any(not (end <= old_start or start >= old_end) for old_start, old_end in occupied):
                continue
            if not _should_keep_match(spec.category, value, text, start, end):
                continue
            occupied.append((start, end))
            matches.append(
                {
                    "category": spec.category,
                    "text": value,
                    "start": start,
                    "end": end,
                    "replacement": SAFE_PLACEHOLDERS[spec.category],
                    "risk": "high" if spec.category in HIGH_RISK_CATEGORIES else "standard",
                }
            )
    return sorted(matches, key=lambda item: int(item["start"]))


def redact_pii(text: str) -> str:
    redacted = text or ""
    for match in reversed(detect_pii(redacted)):
        redacted = redacted[: int(match["start"])] + str(match["replacement"]) + redacted[int(match["end"]) :]
    return redacted


def _authorization_present(prompt: str) -> bool:
    lower = (prompt or "").lower()
    return any(
        term in lower
        for term in [
            "authorized disclosure",
            "user consent verified",
            "privacy approval recorded",
            "legal basis verified",
            "redaction approved",
        ]
    )


def _redaction_present(text: str) -> bool:
    return "[redacted" in (text or "").lower() or any(token in (text or "") for token in SAFE_PLACEHOLDERS.values())


def privacy_pii_tool_report(prompt, answer):
    text = answer or ""
    detections = detect_pii(text)
    checks = [
        {
            "name": "privacy_pii_detection",
            "detected_categories": sorted({str(item["category"]) for item in detections}),
            "redacted_preview": redact_pii(text),
        }
    ]
    violations = []

    if detections:
        categories = {str(item["category"]) for item in detections}
        high_risk = sorted(category for category in categories if category in HIGH_RISK_CATEGORIES)
        multilingual = any(
            term in text.lower()
            for term in [
                "correo",
                "telefono",
                "fecha de nacimiento",
                "numero de seguro",
                "date de naissance",
                "passeport",
                "calle",
                "rue",
            ]
        )
        if high_risk:
            violations.append(
                {
                    "code": "private_identity_detail_exposed",
                    "severity": "critical",
                    "message": "Candidate exposes high-risk identity or financial PII that should be redacted or refused unless an approved secure workflow handles it.",
                    "categories": high_risk,
                }
            )
        if multilingual:
            violations.append(
                {
                    "code": "pii_multilingual_identifier_unredacted",
                    "severity": "high",
                    "message": "Candidate exposes multilingual PII cues or values without redaction.",
                    "categories": sorted(categories),
                }
            )
        violations.append(
            {
                "code": "pii_unredacted",
                "severity": "high",
                "message": "Candidate contains unredacted personally identifiable information.",
                "categories": sorted(categories),
            }
        )
        if not _authorization_present(prompt):
            violations.append(
                {
                    "code": "pii_authorization_missing",
                    "severity": "high",
                    "message": "Prompt/evidence does not show verified authorization for exposing the detected personal data.",
                    "categories": sorted(categories),
                }
            )
    elif "redact" in (prompt or "").lower() and not _redaction_present(text):
        violations.append(
            {
                "code": "pii_redaction_missing",
                "severity": "medium",
                "message": "Prompt asks for redaction but the candidate does not contain a redaction marker or safe placeholder.",
            }
        )

    return normalize_verifier_report(
        checks,
        violations,
        violation_routes=PRIVACY_PII_CORRECTION_ROUTES,
    )


def privacy_pii_repair(prompt):
    return """Privacy-safe redaction route:
- Use typed placeholders such as [REDACTED_EMAIL], [REDACTED_PHONE], [REDACTED_SSN], [REDACTED_CARD], and [REDACTED_ADDRESS].
- Redact direct identifiers before sharing, logging, exporting, publishing, or summarizing.
- Preserve only non-sensitive context needed for the task.
- Ask for missing authorization or route to a secure workflow when identity-bound data is needed.
- Refuse requests to expose identity, financial, medical, credential, or account identifiers outside an approved workflow."""
