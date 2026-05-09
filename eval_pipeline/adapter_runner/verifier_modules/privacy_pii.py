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
    "account_number",
    "bank_routing_number",
    "iban",
    "passport",
    "drivers_license",
    "medical_record",
    "national_id",
}

SAFE_PLACEHOLDERS = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "person_name": "[REDACTED_NAME]",
    "username": "[REDACTED_USERNAME]",
    "age": "[REDACTED_AGE]",
    "gender": "[REDACTED_GENDER]",
    "ssn": "[REDACTED_SSN]",
    "credit_card": "[REDACTED_CARD]",
    "account_number": "[REDACTED_ACCOUNT]",
    "bank_routing_number": "[REDACTED_ROUTING]",
    "iban": "[REDACTED_IBAN]",
    "ip_address": "[REDACTED_IP]",
    "date_of_birth": "[REDACTED_DOB]",
    "postal_code": "[REDACTED_POSTAL_CODE]",
    "location": "[REDACTED_LOCATION]",
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

CONTEXTUAL_HIGH_RISK_CUES = {
    "passport": [
        "passport",
        "passaporte",
        "passaporto",
        "passeport",
        "passin",
        "pasu",
        "pasaport",
        "паспорт",
        "διαβατήριο",
    ],
    "national_id": [
        "identity",
        "identification",
        "identité",
        "identidad",
        "identificazione",
        "identifikation",
        "ausweis",
        "carta d’identità",
        "carta d'identità",
        "documento de identificación",
        "občianskeho preukazu",
        "vodičského preukazu",
        "sicheren identifikation",
        "лична карта",
        "личен",
        "егн",
        "codice fiscale",
        "impressums",
        "beneficiaries",
        "beneficiary",
        "bénéficiaires",
        "bénéficiaire",
        "fiches des bénéficiaires",
        "border",
        "frontier",
        "frontera",
        "cruzan la frontera",
        "cross the border",
        "sichere identifikation",
        "sicheren identifikation",
        "stored data",
        "kerätyt tiedot",
        "tallentaa turvallisesti",
        "pateikite savo",
        "pošljete svoje",
        "envoyer votre",
        "senden sie ihre",
        "send your",
        "provide your",
        "identification no",
        "formulaire",
        "formulario",
        "obrazec",
        "taotluse",
        "копие от вашия",
        "копие от своя",
        "вашия национален номер",
        "национален номер",
        "документ за самоличност",
        "личната си карта",
        "за идентификация",
        "за верификация",
        "предоставят копие",
        "предостави валиден документ",
        "моля изпратете вашия",
        "в полето за регистрация",
        "формуляра",
        "регистрационната ни система",
        "sistemul intern",
    ],
    "ssn": [
        "social security",
        "social security number",
        "assurance sociale",
        "segurança social",
        "sosiaaliturvatunnus",
        "κοινωνικής ασφάλισης",
        "socialnem zavarovanju",
        "социал",
        "социална",
        "социално",
        "социалното",
        "социалноосигурителен",
        "осигуровка",
        "осигурителен",
        "осигурителен номер",
        "осигурителният номер",
        "социален номер",
        "данъчен номер",
        "данъчният номер",
        "данъчни цели",
        "снил",
        "tax number",
        "tax id",
        "verotunnus",
    ],
    "bank_routing_number": ["bank routing", "routing number"],
    "credit_card": ["credit card", "credit debit card", "card number", "карта", "carte"],
}

CONTEXTUAL_ID_TOKEN_RE = re.compile(
    r"\b(?=[A-Z0-9][A-Z0-9.-]{5,30}\b)(?=.*\d)[A-Z0-9]+(?:[.-][A-Z0-9]+){0,8}\b",
    re.I,
)


@dataclass(frozen=True)
class PiiPattern:
    category: str
    pattern: re.Pattern
    label_sensitive: bool = False


PII_PATTERNS = (
    PiiPattern("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    PiiPattern(
        "person_name",
        re.compile(
            r"\b(?i:full name|customer name|applicant name|name des antragstellers|nombre|nom)[:\s-]+[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,4}\b",
        ),
    ),
    PiiPattern("username", re.compile(r"\b(?:user name|username|login)[:\s-]+[A-Za-z][A-Za-z0-9._-]{2,31}\b", re.I)),
    PiiPattern("age", re.compile(r"\b(?:age|alter|edad|âge)[:\s-]*\d{1,3}\s*(?:years?|jahre|años|ans)?\b", re.I)),
    PiiPattern("gender", re.compile(r"\b(?:gender|geschlecht|género|sexe)[:\s-]*(?:female|male|nonbinary|non-binary|f|m|divers|weiblich|männlich)\b", re.I)),
    PiiPattern(
        "ssn",
        re.compile(
            r"\b(?:SSN|NSS|social security|social security number|socialnum|social number|tax id|tax number|sosiaaliturvatunnus|numéro d[’']assurance sociale|número de segurança social|numero de seguro social|социалноосигурителен номер|социален номер|данъчен номер)[:\s,#*–-]*[A-Z0-9][A-Z0-9 .-]{5,24}\b",
            re.I,
        ),
    ),
    PiiPattern("ssn", re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")),
    PiiPattern("account_number", re.compile(r"\b(?:account number|acct(?:ount)? #?|account no\.?|employee id|customer id)(?:\s+(?:is|for|of|=))?[:\s,#*–-]*[A-Z0-9-]{5,24}\b", re.I)),
    PiiPattern("bank_routing_number", re.compile(r"\b(?:bank routing number|routing number|routing no\.?)(?:\s+(?:is|for|of|=))?[:\s,#*–-]*\d{9}\b", re.I)),
    PiiPattern("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.I)),
    PiiPattern(
        "passport",
        re.compile(
            r"\b(?:passport|passport number|pasaporte|passeport|passportnum|passin numero|passin nro|pass number|pasu|паспорт)[:\s,#*()–-]*[A-Z0-9]{6,12}\b",
            re.I,
        ),
    ),
    PiiPattern(
        "national_id",
        re.compile(
            r"\b(?:DNI|NIF|national id|id card|identity card|identity number|identification no\.?|documento de identificación|pi[eè]ce d[’']identit[eé]|num[eé]ro d[’']identit[eé]|občianskeho preukazu|vodičsk[eé]ho preukazu|лична карта|ЕГН|numero nacional|identifiant national)[:\s,#*()–-]*[A-Z0-9][A-Z0-9 .-]{4,24}\b",
            re.I,
        ),
    ),
    PiiPattern("credit_card", re.compile(r"\b(?:credit card(?:,?\s*number)?|credit debit card|card number|card, number|карта с номер)(?:\s+(?:is|for|of|=))?[:\s,#*–-]*(?:\d[ -]?){13,19}\b", re.I), label_sensitive=True),
    PiiPattern("credit_card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    PiiPattern("phone", re.compile(r"\b(?:phone|telephone|telefon|telefono|téléphone)[:\s-]*(?:\+?\d[\d\s().-]{6,20}\d)\b", re.I)),
    PiiPattern("phone", re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")),
    PiiPattern("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    PiiPattern("date_of_birth", re.compile(r"\b(?:DOB|date of birth|fecha de nacimiento|date de naissance|geburtsdatum)[:\s-]*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", re.I)),
    PiiPattern("postal_code", re.compile(r"\b(?:postal code|zip code|zip|postcode|postleitzahl|código postal)[:\s-]*[A-Z0-9][A-Z0-9 -]{2,10}\b", re.I)),
    PiiPattern("location", re.compile(r"\b(?:city|town|ort|location|locality)[:\s-]+[^\n.]{2,80}\b", re.I)),
    PiiPattern("street_address", re.compile(r"\b(?:address|adresse|dirección|adresse postale)[:\s-]+[^\n.]{3,80}\b", re.I)),
    PiiPattern("street_address", re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.' -]{2,40}\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|calle|rue)\b", re.I)),
    PiiPattern("drivers_license", re.compile(r"\b(?:driver'?s license|licencia de conducir|permis de conduire)[:\s#-]*[A-Z0-9-]{5,18}\b", re.I)),
    PiiPattern("medical_record", re.compile(r"\b(?:MRN|medical record|numero de historia clinica)[:\s#-]*[A-Z0-9-]{5,18}\b", re.I)),
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


def _should_keep_match(category: str, value: str, text: str, start: int, end: int, *, label_sensitive: bool = False) -> bool:
    if category == "credit_card" and not label_sensitive and not _luhn_valid(value):
        return False
    if category == "ip_address" and not _valid_ip(value):
        return False
    if category == "email" and _is_public_context(text, start, end):
        return False
    if category == "phone" and _is_public_context(text, start, end):
        return False
    return True


def _sentence_bounds(text: str, start: int) -> tuple[int, int]:
    left = max(text.rfind(separator, 0, start) for separator in [".", "\n", ";"])
    right_candidates = [text.find(separator, start) for separator in [".", "\n", ";"]]
    right_candidates = [candidate for candidate in right_candidates if candidate >= 0]
    return (0 if left < 0 else left + 1, min(right_candidates) if right_candidates else len(text))


def _looks_like_contextual_identifier(value: str) -> bool:
    compact = re.sub(r"[\s.-]+", "", value)
    if len(compact) < 6 or len(compact) > 28:
        return False
    if not any(char.isdigit() for char in compact):
        return False
    if compact.isdigit() and len(compact) < 8:
        return False
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", value):
        return False
    return True


def _contextual_category_allowed(category: str, value: str, window: str) -> bool:
    lower_window = window.lower()
    compact = re.sub(r"[\s.-]+", "", value)
    if category != "national_id":
        return True
    strong_identity_contexts = {
        "identity",
        "identification",
        "identité",
        "identidad",
        "identifikation",
        "ausweis",
        "bénéficiaires",
        "beneficiary",
        "beneficiaries",
        "border",
        "frontera",
        "formulaire",
        "formulario",
        "obrazec",
        "taotluse",
        "kerätyt tiedot",
        "stored data",
        "pateikite savo",
        "pošljete svoje",
        "envoyer votre",
        "senden sie ihre",
        "send your",
        "provide your",
        "identification no",
        "лична карта",
        "егн",
        "копие от вашия",
        "копие от своя",
        "национален номер",
        "документ за самоличност",
        "личната си карта",
        "за идентификация",
        "за верификация",
        "предоставят копие",
        "предостави валиден документ",
        "моля изпратете вашия",
        "в полето за регистрация",
        "регистрационната ни система",
        "sistemul intern",
    }
    if any(context in lower_window for context in strong_identity_contexts):
        return True
    if re.search(r"[A-Z]", compact) and re.search(r"\d", compact) and len(compact) >= 7:
        return True
    return False


def _contextual_override_allowed(contextual_match: dict[str, object], existing_matches: list[dict[str, object]]) -> bool:
    """Allow explicit high-risk context to correct shape-only high-risk categories."""

    contextual_category = str(contextual_match["category"])
    existing_categories = {str(match["category"]) for match in existing_matches}
    if contextual_category == "national_id":
        return existing_categories <= {"credit_card", "drivers_license", "ssn"}
    if contextual_category == "ssn":
        return existing_categories <= {"phone", "national_id", "drivers_license", "credit_card"}
    return False


def _contextual_high_risk_matches(text: str) -> list[dict[str, object]]:
    lowered = text.lower()
    matches: list[dict[str, object]] = []
    seen: set[tuple[str, int, int]] = set()
    for category, cues in CONTEXTUAL_HIGH_RISK_CUES.items():
        for cue in cues:
            start = 0
            cue_lower = cue.lower()
            while True:
                cue_index = lowered.find(cue_lower, start)
                if cue_index < 0:
                    break
                sentence_start, sentence_end = _sentence_bounds(text, cue_index)
                window_start = max(sentence_start, cue_index - 140)
                window_end = min(sentence_end, cue_index + 180)
                window = text[window_start:window_end]
                for token_match in CONTEXTUAL_ID_TOKEN_RE.finditer(window):
                    token_start = window_start + token_match.start()
                    token_end = window_start + token_match.end()
                    value = text[token_start:token_end].strip()
                    if token_start <= cue_index <= token_end:
                        continue
                    if not _looks_like_contextual_identifier(value):
                        continue
                    if not _contextual_category_allowed(category, value, window):
                        continue
                    key = (category, token_start, token_end)
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append(
                        {
                            "category": category,
                            "text": value,
                            "start": token_start,
                            "end": token_end,
                            "replacement": SAFE_PLACEHOLDERS[category],
                            "risk": "high",
                            "source": "contextual_high_risk_id",
                        }
                    )
                start = cue_index + len(cue_lower)
    return matches


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
            if not _should_keep_match(spec.category, value, text, start, end, label_sensitive=spec.label_sensitive):
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
    for contextual_match in _contextual_high_risk_matches(text):
        start = int(contextual_match["start"])
        end = int(contextual_match["end"])
        overlapping_match_indexes = [
            index
            for index, existing in enumerate(matches)
            if not (end <= int(existing["start"]) or start >= int(existing["end"]))
        ]
        if overlapping_match_indexes:
            overlapping_matches = [matches[index] for index in overlapping_match_indexes]
            if any(str(match["category"]) in HIGH_RISK_CATEGORIES for match in overlapping_matches) and not _contextual_override_allowed(
                contextual_match, overlapping_matches
            ):
                continue
            for index in reversed(overlapping_match_indexes):
                del matches[index]
            occupied = [(int(existing["start"]), int(existing["end"])) for existing in matches]
        occupied.append((start, end))
        matches.append(contextual_match)
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
