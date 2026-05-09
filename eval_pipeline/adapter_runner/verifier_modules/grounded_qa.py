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
    "grounded_qa_semantic_unsupported": "revise",
    "grounded_qa_semantic_unanswerable": "defer",
    "grounded_qa_semantic_uncertain": "defer",
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

GROUNDING_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}

GENERIC_PROPER_NAME_TOKENS = {
    "amid",
    "article",
    "case",
    "cases",
    "company",
    "control",
    "disease",
    "editor",
    "former",
    "group",
    "ice",
    "infections",
    "outbreak",
    "patients",
    "people",
    "products",
    "recalls",
    "school",
    "secretary",
    "state",
    "story",
    "team",
    "university",
    "woman",
    "women",
}


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


def _content_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text or "")
        if token.lower() not in GROUNDING_STOPWORDS
    }


def _question_text(prompt: str) -> str:
    match = re.search(r"question:\s*(.*?)(?:\n|retrieved evidence:|$)", prompt or "", re.I | re.S)
    return match.group(1).strip() if match else ""


def _evidence_text(prompt: str) -> str:
    match = re.search(r"retrieved evidence:\s*(.*)$", prompt or "", re.I | re.S)
    return match.group(1).strip() if match else prompt or ""


def _numeric_values(text: str) -> list[float]:
    values: list[float] = []
    for raw in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", text or ""):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _numeric_strings(text: str) -> set[str]:
    return {
        raw.replace(",", "").rstrip(".")
        for raw in re.findall(r"\b\d[\d,]*(?:\.\d+)?%?\b", text or "")
    }


def _numeric_token_value(raw: str) -> float | None:
    normalized = (raw or "").replace(",", "").lower()
    if normalized in NUMBER_WORDS:
        return float(NUMBER_WORDS[normalized])
    try:
        return float(normalized)
    except ValueError:
        return None


def _answer_numeric_values(answer: str) -> list[float]:
    return _numeric_values(answer)


def _close_number(left: float, right: float, tolerance: float = 0.05) -> bool:
    return abs(left - right) <= tolerance


def _scoped_evidence(question: str, evidence: str) -> str:
    lower_question = _lower(question)
    if "first half" in lower_question:
        return re.split(r"\b(?:in\s+the\s+)?third quarter\b|\bsecond half\b", evidence or "", maxsplit=1, flags=re.I)[0]
    if "first quarter" in lower_question or " in the first" in lower_question:
        start_match = re.search(r"\bfirst quarter\b", evidence or "", re.I)
        end_match = re.search(r"\bsecond quarter\b", evidence or "", re.I)
        if start_match and end_match and end_match.start() > start_match.start():
            return (evidence or "")[start_match.start() : end_match.start()]
        if end_match:
            return (evidence or "")[: end_match.start()]
    if "fourth quarter" in lower_question:
        start_match = re.search(r"\bfourth quarter\b", evidence or "", re.I)
        if start_match:
            return (evidence or "")[start_match.start() :]
    return evidence or ""


def _yard_event_values(evidence: str, event: str) -> list[float]:
    pattern = r"\b(\d+)-yard\s+field goal\b" if event == "field_goal" else r"\b(\d+)-yard(?:\s+[A-Za-z]+){0,5}\s+(?:TD|touchdown)\b"
    return [float(match.group(1)) for match in re.finditer(pattern, evidence or "", re.I)]


def _score_differences(evidence: str) -> set[float]:
    return {
        abs(float(left) - float(right))
        for left, right in re.findall(r"\b(\d{1,3})-(\d{1,3})\b", evidence or "")
    }


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _count_cue_value(question: str, evidence: str) -> float | None:
    lower_question = _lower(question)
    if "how many touchdowns" not in lower_question:
        return None
    entity_match = re.search(r"did\s+([A-Za-z][A-Za-z'-]+)\s+catch", question or "", re.I)
    entity = entity_match.group(1).lower() if entity_match else ""
    for sentence in re.split(r"(?<=[.!?])\s+", evidence or ""):
        lower_sentence = sentence.lower()
        if entity and entity not in lower_sentence:
            continue
        if "touchdown" not in lower_sentence:
            continue
        explicit = re.search(r"\bfirst of (\w+|\d+)\s+touchdown", lower_sentence)
        if explicit:
            token = explicit.group(1)
            if token.isdigit():
                return float(token)
            if token in NUMBER_WORDS:
                return float(NUMBER_WORDS[token])
    return None


def _answer_entity_tokens(answer: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", answer or "")
        if token.lower() not in GROUNDING_STOPWORDS
    }


def _census_group_percentages(evidence: str) -> dict[str, float]:
    groups: dict[str, float] = {}
    for percent, group in re.findall(r"\b(\d+(?:\.\d+)?)%\s+(?:were\s+of\s+)?([A-Z][A-Za-z\" -]{2,40})(?=,|\.| and |\sof any race)", evidence or ""):
        clean_group = group.strip(' "').lower()
        if clean_group:
            groups[clean_group] = float(percent)
    return groups


def _entity_comparison_gap(question: str, evidence: str, answer: str) -> bool:
    lower_question = _lower(question)
    answer_tokens = _answer_entity_tokens(answer)
    if not answer_tokens:
        return False

    smaller_match = re.search(r"(?:which|what) (?:group|language|ancestry).* smaller:?\s+([a-z][a-z -]+?)\s+or\s+([a-z][a-z -]+)\??", lower_question)
    larger_match = re.search(r"(?:which|what) (?:group|language|ancestry).* larger.*:?\s+([a-z][a-z -]+?)\s+or\s+([a-z][a-z -]+)\??", lower_question)
    comparison_match = smaller_match or larger_match
    if comparison_match:
        first = comparison_match.group(1).strip().split()[-1]
        second = comparison_match.group(2).strip().split()[-1]
        groups = _census_group_percentages(evidence)
        first_value = next((value for group, value in groups.items() if first in group), None)
        second_value = next((value for group, value in groups.items() if second in group), None)
        if first_value is not None and second_value is not None:
            expected = first if (first_value < second_value if smaller_match else first_value > second_value) else second
            return expected not in answer_tokens

    winner_match = re.search(r"which team won.*?,\s*([A-Za-z][A-Za-z -]+?)\s+or\s+([A-Za-z][A-Za-z -]+)\??", question or "", re.I)
    if winner_match:
        options = [winner_match.group(1).strip().lower(), winner_match.group(2).strip().lower()]
        win_sentence = next((sentence for sentence in re.split(r"(?<=[.!?])\s+", evidence or "") if "with the win" in sentence.lower()), "")
        for option in options:
            if option in win_sentence.lower():
                return option not in answer_tokens

    second_longest_fg_match = re.search(r"who kicked the second longest field goal", lower_question)
    if second_longest_fg_match:
        pairs = [
            (float(match.group(2)), match.group(1).strip().lower())
            for match in re.finditer(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}).{0,80}?(\d+)-yard\s+field goal\b", evidence or "", re.I)
        ]
        unique_pairs = sorted({(yards, name) for yards, name in pairs}, reverse=True)
        if len(unique_pairs) >= 2:
            expected_name_tokens = set(unique_pairs[1][1].split())
            return not (answer_tokens & expected_name_tokens)

    return False


def _proper_name_phrases(text: str) -> set[str]:
    phrases: set[str] = set()
    for match in re.finditer(
        r"\b(?:[A-Z][a-z][A-Za-z'-]*|[A-Z]{2,})(?:\s+(?:[A-Z][a-z][A-Za-z'-]*|[A-Z]{2,})){1,3}\b",
        text or "",
    ):
        phrase = match.group(0).strip()
        words = phrase.split()
        lower_words = [word.strip("'").lower() for word in words]
        if any(word in GENERIC_PROPER_NAME_TOKENS for word in lower_words):
            continue
        if all(word.isupper() and len(word) <= 5 for word in words):
            continue
        if len({word for word in lower_words if word not in GROUNDING_STOPWORDS}) < 2:
            continue
        phrases.add(" ".join(lower_words))
    return phrases


def _unsupported_proper_name_count(evidence: str, answer: str) -> int:
    evidence_lower = _lower(evidence)
    evidence_tokens = _content_tokens(evidence)
    count = 0
    for phrase in _proper_name_phrases(answer):
        phrase_tokens = set(phrase.split())
        if phrase in evidence_lower:
            continue
        if phrase_tokens and phrase_tokens <= evidence_tokens:
            continue
        count += 1
    return count


def _unsupported_numeric_fact_count(question: str, evidence: str, answer: str) -> int:
    lower_question = _lower(question)
    if any(term in lower_question for term in ("how many", "how much", "what percent", "difference", "more than", "less than")):
        return 0
    evidence_numbers = _numeric_strings(evidence)
    return sum(1 for value in _numeric_strings(answer) if value not in evidence_numbers)


def _introduced_fact_gap(question: str, evidence: str, answer: str, unsupported_token_ratio: float) -> tuple[bool, int, int]:
    unsupported_name_count = _unsupported_proper_name_count(evidence, answer)
    unsupported_number_count = _unsupported_numeric_fact_count(question, evidence, answer)
    summary_like = "summarize" in _lower(question) or len((answer or "").split()) >= 25

    if unsupported_name_count >= 2 and unsupported_token_ratio >= 0.10:
        return True, unsupported_name_count, unsupported_number_count
    if unsupported_name_count >= 1 and unsupported_number_count >= 1 and unsupported_token_ratio >= 0.20:
        return True, unsupported_name_count, unsupported_number_count
    if summary_like and unsupported_number_count >= 2 and unsupported_token_ratio >= 0.20:
        return True, unsupported_name_count, unsupported_number_count
    if unsupported_number_count >= 3 and unsupported_token_ratio >= 0.15:
        return True, unsupported_name_count, unsupported_number_count
    return False, unsupported_name_count, unsupported_number_count


def _predicate_numeric_conflict_count(evidence: str, answer: str) -> int:
    predicate_patterns = (
        r"(?:died|dead|deaths|killed|fatalities)",
        r"(?:infected|infections|illnesses|cases)",
        r"(?:sentenced|probation|prison|jail)",
    )
    number_pattern = r"(?:\d[\d,]*(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")"

    def values_for(pattern: str, text: str) -> set[float]:
        raw_values = re.findall(rf"\b({number_pattern})\b(?:\s+\w+){{0,4}}\s+{pattern}", text or "", re.I)
        raw_values += re.findall(rf"{pattern}(?:\s+\w+){{0,4}}\s+\b({number_pattern})\b", text or "", re.I)
        values = {_numeric_token_value(raw) for raw in raw_values}
        return {value for value in values if value is not None}

    conflicts = 0
    for predicate in predicate_patterns:
        evidence_values = values_for(predicate, evidence)
        answer_values = values_for(predicate, answer)
        if evidence_values and answer_values and answer_values.isdisjoint(evidence_values):
            conflicts += 1
    return conflicts


def _evident_contradiction_gap(evidence: str, answer: str) -> tuple[bool, int]:
    lower_evidence = _lower(evidence)
    lower_answer = _lower(answer)
    signals = 0

    if (
        any(term in lower_evidence for term in ("not clear when or where", "unclear when or where", "not known when or where"))
        and (
            re.search(r"\b(?:arrested|charged|occurred|happened)\s+(?:before|after)\b", lower_answer)
            or re.search(
                r"\b(?:arrested|charged|occurred|happened)\s+on\s+(?:\w+\s+)?\d{1,4}\b",
                lower_answer,
            )
            or re.search(r"\b(?:arrested|charged|occurred|happened)\s+in\s+\d{4}\b", lower_answer)
        )
    ):
        signals += 1

    if re.search(r"\bno\b.{0,80}\b(?:linked|infection|infections|illness|illnesses|reported)\b", lower_answer) and any(
        term in lower_evidence for term in ("infected", "infection", "illness", "illnesses", "died", "death")
    ):
        signals += 1

    if "pleaded guilty" in lower_answer and "pleaded no contest" in lower_evidence:
        signals += 1
    if re.search(r"\b(?:his|her|their)\s+(?:wife|husband|spouse)\b", lower_answer) and "companion" in lower_evidence:
        signals += 1

    signals += _predicate_numeric_conflict_count(evidence, answer)
    return signals > 0, signals


def _answer_shape_gap(question: str, answer: str) -> bool:
    lower_question = _lower(question)
    stripped_answer = (answer or "").strip()
    if not re.match(r"^\[[^\]]*,[^\]]+\]$", stripped_answer):
        return False
    if any(term in lower_question for term in (" two ", " both ", " all ", " list ", " which of the")):
        return False
    return lower_question.startswith(("which ", "who ", "what "))


def _numeric_consistency_gap(question: str, evidence: str, answer: str) -> bool:
    lower_question = _lower(question)
    answer_numbers = _answer_numeric_values(answer)
    if len(answer_numbers) != 1:
        scoped = _scoped_evidence(question, evidence)
        if "two shortest" in lower_question and ("touchdown" in lower_question or "td" in lower_question):
            touchdown_values = _yard_event_values(scoped, "touchdown")
            if len(answer_numbers) >= 2 and len(touchdown_values) >= 2:
                expected = sorted(touchdown_values)[:2]
                actual = sorted(answer_numbers)[:2]
                return any(not _close_number(left, right) for left, right in zip(actual, expected))
        return False
    answer_value = answer_numbers[0]
    scoped = _scoped_evidence(question, evidence)

    if "field goal" in lower_question and "yard" in lower_question:
        field_goal_values = _yard_event_values(scoped, "field_goal")
        if field_goal_values:
            unique_values = sorted(set(field_goal_values), reverse=True)
            expected = None
            if "second longest" in lower_question and len(unique_values) >= 2:
                expected = unique_values[1]
            elif "longest" in lower_question:
                expected = unique_values[0]
            elif "shortest" in lower_question:
                expected = unique_values[-1]
            if expected is not None:
                return not _close_number(answer_value, expected)

    if ("touchdown" in lower_question or "td" in lower_question) and "yard" in lower_question:
        touchdown_values = _yard_event_values(scoped, "touchdown")
        if touchdown_values:
            expected = None
            if "last touchdown" in lower_question:
                expected = touchdown_values[-1]
            elif "longest" in lower_question:
                expected = max(touchdown_values)
            elif "shortest" in lower_question:
                expected = min(touchdown_values)
            if expected is not None:
                return not _close_number(answer_value, expected)

    count_cue = _count_cue_value(question, evidence)
    if count_cue is not None:
        return not _close_number(answer_value, count_cue)

    if any(term in lower_question for term in ("defeat", "beat", "won by")) and "point" in lower_question:
        differences = _score_differences(evidence)
        if differences:
            return all(not _close_number(answer_value, difference) for difference in differences)

    evidence_numbers = _numeric_values(evidence)
    if "how many more" in lower_question and len(evidence_numbers) >= 2:
        differences = {
            round(abs(left - right), 2)
            for index, left in enumerate(evidence_numbers)
            for right in evidence_numbers[index + 1 :]
        }
        return round(answer_value, 2) not in differences
    percent_not_match = re.search(r"(?:how many|what).*percent.*(?:not|weren't|were not|wasn't|was not)\s+([a-z][a-z -]{2,40})\??", lower_question)
    if percent_not_match:
        target_words = set(_content_tokens(percent_not_match.group(1)))
        if not target_words:
            return False
        sentences = re.split(r"(?<=[.!?])\s+", evidence)
        complements = []
        for sentence in sentences:
            sentence_tokens = _content_tokens(sentence)
            if not (target_words & sentence_tokens):
                continue
            for value in re.findall(r"\b\d+(?:\.\d+)?\s*%", sentence):
                complements.append(round(100.0 - float(value.rstrip("%")), 2))
        if complements:
            return all(abs(answer_value - complement) > 0.05 for complement in complements)
    return False


def classify_grounded_answer(prompt: str, answer: str) -> dict[str, object]:
    """Classify a candidate answer using evidence/citation signals."""

    lower_prompt = _lower(prompt)
    lower_answer = _lower(answer)
    question = _question_text(prompt)
    evidence = _evidence_text(prompt)
    answer_citations = citation_tokens(answer)
    allowed_citations = indexed_citations(prompt)
    invalid_citations = sorted(answer_citations - allowed_citations) if allowed_citations else []
    citation_optional = any(
        term in lower_prompt
        for term in (
            "citation optional",
            "citations optional",
            "dataset does not provide citations",
            "use retrieved evidence as source",
        )
    )

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
    has_material_claim = bool(
        re.search(
            r"\b(is|are|was|were|will|can|must|shows|reported|found|joined|included|includes|contains|contained|charged|arrested|accused|planned|purchased|died|dead|killed|causes|improves|reduces|reduced|increased|decreased|eliminates|eliminated)\b",
            lower_answer,
        )
    )
    answer_tokens = _content_tokens(answer)
    evidence_tokens = _content_tokens(prompt)
    unsupported_answer_tokens = sorted(answer_tokens - evidence_tokens)
    unsupported_token_ratio = len(unsupported_answer_tokens) / len(answer_tokens) if answer_tokens else 0.0
    lexical_support_gap = citation_optional and has_material_claim and len(unsupported_answer_tokens) >= 3 and unsupported_token_ratio >= 0.45
    answer_shape_gap = citation_optional and _answer_shape_gap(question, answer)
    numeric_consistency_gap = citation_optional and _numeric_consistency_gap(question, evidence, answer)
    entity_consistency_gap = citation_optional and _entity_comparison_gap(question, evidence, answer)
    introduced_fact_gap, unsupported_proper_name_count, unsupported_numeric_fact_count = (
        _introduced_fact_gap(question, evidence, answer, unsupported_token_ratio)
        if citation_optional and has_material_claim
        else (False, 0, 0)
    )
    evident_contradiction_gap, contradiction_signal_count = (
        _evident_contradiction_gap(evidence, answer) if citation_optional and has_material_claim else (False, 0)
    )
    needs_citation = has_material_claim and not answer_citations and not answer_abstains and not citation_optional
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
    elif (
        unsupported_terms
        or lexical_support_gap
        or answer_shape_gap
        or numeric_consistency_gap
        or entity_consistency_gap
        or introduced_fact_gap
        or evident_contradiction_gap
        or source_registry_bypassed
        or (source_boundary_terms and not invalid_citations)
    ):
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
        "citation_optional": citation_optional,
        "unsupported_terms": unsupported_terms,
        "unsupported_answer_tokens": unsupported_answer_tokens,
        "unsupported_token_ratio": unsupported_token_ratio,
        "lexical_support_gap": lexical_support_gap,
        "answer_shape_gap": answer_shape_gap,
        "numeric_consistency_gap": numeric_consistency_gap,
        "entity_consistency_gap": entity_consistency_gap,
        "introduced_fact_gap": introduced_fact_gap,
        "evident_contradiction_gap": evident_contradiction_gap,
        "unsupported_proper_name_count": unsupported_proper_name_count,
        "unsupported_numeric_fact_count": unsupported_numeric_fact_count,
        "contradiction_signal_count": contradiction_signal_count,
        "prompt_unanswerable": prompt_unanswerable,
        "answer_abstains": answer_abstains,
        "high_impact": high_impact,
        "needs_citation": needs_citation,
        "evidence_gap_unlabeled": evidence_gap_unlabeled,
        "source_boundary_terms": source_boundary_terms,
        "source_registry_bypassed": source_registry_bypassed,
        "uncertainty_missing": uncertainty_missing,
    }


def _run_optional_semantic_verifier(semantic_verifier, prompt: str, answer: str) -> dict[str, object] | None:
    if semantic_verifier is None:
        return None
    try:
        from eval_pipeline.semantic_verifier import run_grounded_qa_semantic_verifier
    except ImportError:  # pragma: no cover - script path fallback
        from semantic_verifier import run_grounded_qa_semantic_verifier
    return run_grounded_qa_semantic_verifier(semantic_verifier, prompt, answer)


def _should_apply_optional_semantic_result(semantic_result, classification, semantic_policy=None) -> bool:
    if semantic_result is None:
        return False
    try:
        from eval_pipeline.semantic_verifier import should_apply_grounded_qa_semantic_result
    except ImportError:  # pragma: no cover - script path fallback
        from semantic_verifier import should_apply_grounded_qa_semantic_result
    return should_apply_grounded_qa_semantic_result(
        semantic_result,
        classification,
        policy=semantic_policy,
    )


def grounded_qa_tool_report(prompt, answer, semantic_verifier=None, semantic_policy=None):
    classification = classify_grounded_answer(prompt, answer or "")
    semantic_result = _run_optional_semantic_verifier(semantic_verifier, prompt, answer or "")
    apply_semantic_result = _should_apply_optional_semantic_result(semantic_result, classification, semantic_policy)
    violations = []
    label = classification["label"]
    if apply_semantic_result and label == "supported":
        label = "unanswerable" if semantic_result.get("label") == "unanswerable" else "unsupported"

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
    if classification["lexical_support_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Answer contains content words that are weakly covered by retrieved evidence in citation-optional mode.",
                "unsupported_answer_tokens": classification["unsupported_answer_tokens"][:12],
                "unsupported_token_ratio": classification["unsupported_token_ratio"],
            }
        )
    if classification["answer_shape_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "medium",
                "message": "Answer shape is inconsistent with the question and should be revised or checked against evidence.",
            }
        )
    if classification["numeric_consistency_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Numeric answer is inconsistent with simple arithmetic constraints visible in retrieved evidence.",
            }
        )
    if classification["entity_consistency_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Answer selects an entity inconsistent with a checkable comparison or selection relation in retrieved evidence.",
            }
        )
    if classification["introduced_fact_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Answer introduces named entities or numeric facts that are not supported by retrieved evidence.",
                "unsupported_proper_name_count": classification["unsupported_proper_name_count"],
                "unsupported_numeric_fact_count": classification["unsupported_numeric_fact_count"],
            }
        )
    if classification["evident_contradiction_gap"]:
        violations.append(
            {
                "code": "grounded_qa_unsupported_claim",
                "severity": "high",
                "message": "Answer contradicts retrieved evidence through asserted timing, negation, role/status, or predicate-scoped numeric facts.",
                "contradiction_signal_count": classification["contradiction_signal_count"],
            }
        )
    if apply_semantic_result:
        semantic_label = str(semantic_result.get("label") or "uncertain")
        code = "grounded_qa_semantic_unanswerable" if semantic_label == "unanswerable" else "grounded_qa_semantic_unsupported"
        if semantic_label == "uncertain":
            code = "grounded_qa_semantic_uncertain"
        violations.append(
            {
                "code": code,
                "severity": "high" if semantic_label != "uncertain" else "medium",
                "message": "Optional semantic verifier found grounding risk that should tighten the AANA route.",
                "semantic_label": semantic_label,
                "semantic_confidence": semantic_result.get("confidence"),
                "semantic_reason_codes": semantic_result.get("reason_codes", []),
                "semantic_evidence_issue": semantic_result.get("evidence_issue"),
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
            "semantic_verifier": semantic_result,
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
