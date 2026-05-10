#!/usr/bin/env python
"""Write audit-safe context diagnostics for Privacy/PII category misses.

This script reloads the registered held-out rows transiently, masks
dataset-provided spans, and writes only cue words and category metadata. It is
for calibration diagnostics; raw source text is never persisted.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
import time
from collections import Counter
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from scripts.hf.run_privacy_pii_hf_experiment import (  # noqa: E402
    DEFAULT_EXPERIMENT,
    _fetch_hf_rows_batched,
    _load_json,
    _normalize_label,
)
from adapter_runner.verifier_modules.privacy_pii import HIGH_RISK_CATEGORIES  # noqa: E402


DEFAULT_INPUT = ROOT / "eval_outputs" / "privacy_pii_hf_experiment_live_300_v2_ssn_context.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "privacy_pii_safe_miss_inspection_ssn.json"

CONTEXT_CLUSTERS = {
    "submit_send_copy": (
        "send",
        "senden",
        "provide",
        "present",
        "fournir",
        "изпрат",
        "представ",
        "подав",
        "копие",
    ),
    "tax_social_insurance": (
        "ssn",
        "social",
        "security",
        "insurance",
        "tax",
        "assurance",
        "segurança",
        "социал",
        "социална",
        "осигур",
        "осигуровка",
        "данъчен",
        "данъчни",
        "снил",
    ),
    "identity_verification": (
        "identity",
        "identification",
        "verify",
        "verification",
        "лична",
        "иденти",
        "самоличност",
        "верификация",
        "валид",
    ),
    "forms_registration": (
        "form",
        "formular",
        "application",
        "request",
        "registration",
        "формуляр",
        "регистрац",
        "заяв",
        "иск",
    ),
    "records_internal_system": (
        "record",
        "records",
        "system",
        "stored",
        "data",
        "систем",
        "данни",
        "вътреш",
        "sistemul",
        "intern",
    ),
    "benefit_grant_funding": (
        "benefit",
        "beneficiary",
        "grant",
        "funding",
        "финанс",
        "помощ",
        "förderung",
    ),
    "travel_border_or_event_access": (
        "border",
        "frontier",
        "travel",
        "passport",
        "event",
        "reserve",
        "booking",
        "събит",
        "резерв",
        "полет",
    ),
    "health_or_biometric": (
        "health",
        "medical",
        "fingerprint",
        "portal",
        "здрав",
        "биометр",
    ),
}

EXPLICIT_SSN_CUES = {
    "ssn",
    "social",
    "security",
    "insurance",
    "tax",
    "assurance",
    "segurança",
    "социал",
    "социална",
    "осигур",
    "осигуровка",
    "данъчен",
    "данъчни",
    "снил",
}

GENERIC_ID_CUES = {
    "id",
    "identity",
    "identification",
    "reference",
    "code",
    "номер",
    "данни",
    "data",
    "document",
    "документ",
}


def _coerce_entities(entities: Any) -> list[dict[str, Any]]:
    if isinstance(entities, str):
        try:
            entities = ast.literal_eval(entities)
        except (SyntaxError, ValueError):
            return []
    return [entity for entity in entities or [] if isinstance(entity, dict)]


def _row_id(dataset_name: str, row: dict[str, Any], index: int) -> str:
    return str(row.get("uid") or f"{dataset_name}:{index}")


def _entity_span(entity: dict[str, Any], text: str) -> tuple[int, int] | None:
    start = entity.get("start")
    end = entity.get("end")
    if start is None:
        start = entity.get("start_offset") or entity.get("start_idx")
    if end is None:
        end = entity.get("end_offset") or entity.get("end_idx")
    try:
        start_int = int(start)
        end_int = int(end)
    except (TypeError, ValueError):
        value = str(entity.get("value") or "")
        if not value:
            return None
        found = text.find(value)
        if found < 0:
            return None
        return found, found + len(value)
    if start_int < 0 or end_int <= start_int or end_int > len(text):
        return None
    return start_int, end_int


def _entities_with_categories(dataset: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(row.get(dataset["text_field"]) or "")
    entities = []
    for entity in _coerce_entities(row.get(dataset["label_field"])):
        category = _normalize_label(str(entity.get("label") or ""), text)
        span = _entity_span(entity, text)
        if category and span:
            entities.append({"category": category, "start": span[0], "end": span[1]})
    return entities


def _mask_spans(text: str, entities: list[dict[str, Any]], target_category: str) -> str:
    masked = text
    for entity in sorted(entities, key=lambda item: int(item["start"]), reverse=True):
        replacement = f"[EXPECTED_{target_category.upper()}]" if entity["category"] == target_category else "[EXPECTED_PII]"
        masked = masked[: int(entity["start"])] + replacement + masked[int(entity["end"]) :]
    return masked


def _safe_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[\wÀ-žА-Яа-я]+", text, re.UNICODE)
    safe: list[str] = []
    for token in tokens:
        if token.startswith("EXPECTED_"):
            continue
        if any(char.isdigit() for char in token):
            continue
        if "@" in token:
            continue
        if len(token) < 3:
            continue
        safe.append(token.lower())
    return safe


def _context_clusters(cue_words: list[str]) -> list[str]:
    token_set = set(cue_words)
    clusters = [name for name, cues in CONTEXT_CLUSTERS.items() if token_set & set(cues)]
    return clusters or ["unclustered"]


def _category_ambiguity_likely(
    *,
    target_category: str,
    detected_categories: set[str],
    cue_words: list[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    token_set = set(cue_words)
    alternate_high_risk = sorted((detected_categories & HIGH_RISK_CATEGORIES) - {target_category})
    if alternate_high_risk:
        reasons.append(f"alternate_high_risk_detected:{','.join(alternate_high_risk)}")
    if target_category == "ssn" and not (token_set & EXPLICIT_SSN_CUES):
        reasons.append("missing_explicit_tax_social_insurance_cue")
    if target_category == "ssn" and token_set & GENERIC_ID_CUES and not (token_set & EXPLICIT_SSN_CUES):
        reasons.append("generic_identity_or_reference_context")
    return bool(reasons), reasons


def _load_raw_rows(experiment: dict[str, Any], *, offset: int, max_rows_per_source: int) -> dict[str, dict[str, Any]]:
    raw_rows: dict[str, dict[str, Any]] = {}
    for dataset in experiment.get("datasets", []):
        rows = []
        for attempt in range(3):
            try:
                rows = _fetch_hf_rows_batched(
                    dataset["dataset_name"],
                    dataset["config"],
                    dataset["split"],
                    offset=offset,
                    length=max_rows_per_source,
                )
                break
            except (OSError, TimeoutError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Failed to fetch {dataset['dataset_name']} after retries: {exc}") from exc
                time.sleep(2 + attempt)
        for index, row in enumerate(rows):
            raw_rows[_row_id(dataset["dataset_name"], row, index)] = {"dataset": dataset, "row": row}
    return raw_rows


def inspect_misses(
    *,
    result_payload: dict[str, Any],
    experiment: dict[str, Any],
    target_category: str,
    offset: int,
    max_rows_per_source: int,
    cue_window_chars: int,
) -> dict[str, Any]:
    raw_rows = _load_raw_rows(experiment, offset=offset, max_rows_per_source=max_rows_per_source)
    rows: list[dict[str, Any]] = []
    cluster_counts = Counter()
    ambiguity_counts = Counter()

    for result_row in result_payload.get("rows", []):
        expected_categories = set(result_row.get("expected_categories") or [])
        detected_categories = set(result_row.get("detected_categories") or [])
        if target_category not in expected_categories or target_category in detected_categories:
            continue
        raw = raw_rows.get(str(result_row.get("id")))
        if not raw:
            continue
        dataset = raw["dataset"]
        row = raw["row"]
        text = str(row.get(dataset["text_field"]) or "")
        entities = _entities_with_categories(dataset, row)
        target_spans = [entity for entity in entities if entity["category"] == target_category]
        if not target_spans:
            continue

        masked_text = _mask_spans(text, entities, target_category)
        cue_words: list[str] = []
        for span in target_spans:
            start = max(0, int(span["start"]) - cue_window_chars)
            end = min(len(masked_text), int(span["end"]) + cue_window_chars)
            cue_words.extend(_safe_tokens(masked_text[start:end]))
        cue_words = sorted(set(cue_words))
        clusters = _context_clusters(cue_words)
        ambiguity_likely, ambiguity_reasons = _category_ambiguity_likely(
            target_category=target_category,
            detected_categories=detected_categories,
            cue_words=cue_words,
        )
        for cluster in clusters:
            cluster_counts[cluster] += 1
        ambiguity_counts["likely" if ambiguity_likely else "not_likely"] += 1
        rows.append(
            {
                "id": result_row.get("id"),
                "source_dataset": result_row.get("source_dataset"),
                "expected_category": target_category,
                "detected_categories": sorted(detected_categories),
                "language": result_row.get("language"),
                "surrounding_cue_words": cue_words,
                "context_clusters": clusters,
                "category_ambiguity_likely": ambiguity_likely,
                "ambiguity_reasons": ambiguity_reasons,
            }
        )

    return {
        "schema_version": "0.1",
        "artifact_type": "privacy_pii_safe_miss_inspection",
        "raw_pii_storage": "No raw source text is stored. Dataset-provided spans are masked transiently; output contains only categories, languages, cue words, clusters, and ambiguity flags.",
        "source_result_artifact": result_payload.get("experiment_id"),
        "detector_version": result_payload.get("detector_version"),
        "target_category": target_category,
        "miss_count": len(rows),
        "cluster_counts": dict(sorted(cluster_counts.items())),
        "ambiguity_counts": dict(sorted(ambiguity_counts.items())),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--experiment", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--target-category", default="ssn")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-rows-per-source", type=int, default=300)
    parser.add_argument("--cue-window-chars", type=int, default=90)
    args = parser.parse_args(argv)

    result_payload = _load_json(pathlib.Path(args.input))
    experiment = _load_json(pathlib.Path(args.experiment))
    report = inspect_misses(
        result_payload=result_payload,
        experiment=experiment,
        target_category=args.target_category,
        offset=args.offset,
        max_rows_per_source=args.max_rows_per_source,
        cue_window_chars=args.cue_window_chars,
    )
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "pass -- "
        f"target={report['target_category']} misses={report['miss_count']} "
        f"ambiguous={report['ambiguity_counts'].get('likely', 0)} output={output_path}"
    )
    for cluster, count in report["cluster_counts"].items():
        print(f"- {cluster}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
