#!/usr/bin/env python
"""Train the lightweight AANA Privacy/PII v2 token/span model.

Only calibration splits are used:
- ai4privacy/pii-masking-openpii-1m default/train
- nvidia/Nemotron-PII default/train
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from eval_pipeline.hf_dataset_registry import load_registry  # noqa: E402
from adapter_runner.verifier_modules.privacy_pii_v2 import token_features, tokenize_for_pii  # noqa: E402
from scripts.hf.run_privacy_pii_hf_experiment import (  # noqa: E402
    _fetch_hf_rows,
    _normalize_label,
)


DEFAULT_OUTPUT = ROOT / "eval_outputs" / "privacy_pii_v2_model.json"
DEFAULT_TOKEN_MODEL = ROOT / "eval_outputs" / "privacy_pii_v2_token_model.joblib"
DEFAULT_REPORT = ROOT / "eval_outputs" / "privacy_pii_v2_training_report.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"

CALIBRATION_SOURCES = [
    {
        "dataset_name": "ai4privacy/pii-masking-openpii-1m",
        "config": "default",
        "split": "train",
        "text_field": "source_text",
        "label_field": "privacy_mask",
        "kind": "openpii",
    },
    {
        "dataset_name": "nvidia/Nemotron-PII",
        "config": "default",
        "split": "train",
        "text_field": "text",
        "label_field": "spans",
        "kind": "nemotron",
    },
]


def _fetch_calibration_rows(source: dict[str, str], offset: int, length: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    remaining = length
    current_offset = offset
    while remaining > 0:
        batch_length = min(100, remaining)
        batch = _fetch_hf_rows(
            source["dataset_name"],
            source["config"],
            source["split"],
            offset=current_offset,
            length=batch_length,
        )
        rows.extend(batch)
        if len(batch) < batch_length:
            break
        current_offset += batch_length
        remaining -= batch_length
    return rows


def _parse_entities(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return value if isinstance(value, list) else []


def _clean_cue(text: str) -> str | None:
    cue = re.sub(r"\s+", " ", text.strip(" \t\r\n:-,;()[]{}")).strip()
    if len(cue) < 3 or len(cue) > 42:
        return None
    if not any(char.isalpha() for char in cue):
        return None
    if len(cue.split()) > 6:
        return None
    return cue.lower()


def _cue_before_span(text: str, start: int) -> str | None:
    prefix = text[max(0, start - 80) : start]
    for separator in ("\n", ".", ";"):
        if separator in prefix:
            prefix = prefix.rsplit(separator, 1)[-1]
    if ":" in prefix:
        prefix = prefix.rsplit(":", 1)[0]
    return _clean_cue(prefix)


def _token_labels(text: str, entities: list[dict[str, Any]]) -> tuple[list[dict[str, object]], list[str], int]:
    tokens = tokenize_for_pii(text)
    labels = ["O"] * len(tokens)
    mapped = 0
    spans: list[tuple[int, int, str]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        category = _normalize_label(str(entity.get("label") or ""), text)
        start = entity.get("start")
        end = entity.get("end")
        if not category or not isinstance(start, int) or not isinstance(end, int):
            continue
        spans.append((start, end, category))
    for index, token in enumerate(tokens):
        token_start = int(token["start"])
        token_end = int(token["end"])
        for start, end, category in spans:
            if token_start < end and token_end > start:
                labels[index] = category
                mapped += 1
                break
    return tokens, labels, mapped


def _split_allowed_for_calibration(registry: dict[str, Any], source: dict[str, str]) -> bool:
    for dataset in registry.get("datasets", []):
        if dataset.get("dataset_name") != source["dataset_name"]:
            continue
        for split_use in dataset.get("split_uses", []):
            if (
                split_use.get("config") == source["config"]
                and split_use.get("split") == source["split"]
                and split_use.get("allowed_use") == "calibration"
            ):
                return True
    return False


def train_model(
    max_rows_per_source: int,
    offset: int,
    min_cue_count: int,
    registry_path: pathlib.Path,
    token_model_path: pathlib.Path,
    max_o_multiplier: int,
    token_min_probability: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_registry(registry_path)
    for source in CALIBRATION_SOURCES:
        if not _split_allowed_for_calibration(registry, source):
            raise ValueError(f"Calibration split is not registered: {source['dataset_name']} {source['config']}/{source['split']}")

    cue_counts: dict[str, Counter] = defaultdict(Counter)
    rows_seen = 0
    entities_seen = 0
    mapped_entities = 0
    token_rows: list[dict[str, object]] = []
    token_labels: list[str] = []
    positive_token_count = 0
    o_token_count = 0
    source_reports = []
    for source in CALIBRATION_SOURCES:
        rows = _fetch_calibration_rows(source, offset=offset, length=max_rows_per_source)
        source_entities = 0
        source_mapped = 0
        for row in rows:
            rows_seen += 1
            text = str(row.get(source["text_field"]) or "")
            entities = _parse_entities(row.get(source["label_field"]))
            tokens, labels, mapped_tokens = _token_labels(text, entities)
            positive_token_count += mapped_tokens
            for index, label in enumerate(labels):
                if label == "O":
                    if positive_token_count and o_token_count >= max_o_multiplier * max(positive_token_count, 1):
                        continue
                    o_token_count += 1
                token_rows.append(token_features(tokens, index, text))
                token_labels.append(label)
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entities_seen += 1
                source_entities += 1
                category = _normalize_label(str(entity.get("label") or ""), text)
                if not category:
                    continue
                start = entity.get("start")
                if not isinstance(start, int):
                    continue
                cue = _cue_before_span(text, start)
                if not cue:
                    continue
                cue_counts[category][cue] += 1
                mapped_entities += 1
                source_mapped += 1
        source_reports.append(
            {
                "dataset_name": source["dataset_name"],
                "config": source["config"],
                "split": source["split"],
                "allowed_use": "calibration",
                "rows_seen": len(rows),
                "entities_seen": source_entities,
                "mapped_cue_entities": source_mapped,
            }
        )

    field_cues = {
        category: [
            cue
            for cue, count in counts.most_common(80)
            if count >= min_cue_count or max_rows_per_source <= 25
        ]
        for category, counts in sorted(cue_counts.items())
    }
    field_cues = {category: cues for category, cues in field_cues.items() if cues}
    token_report: dict[str, Any] = {
        "status": "not_trained",
        "token_rows": len(token_rows),
        "positive_token_count": positive_token_count,
        "o_token_count": o_token_count,
    }
    if token_rows and any(label != "O" for label in token_labels):
        from joblib import dump
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline

        classifier = make_pipeline(
            DictVectorizer(sparse=True),
            LogisticRegression(max_iter=900, class_weight="balanced", solver="lbfgs"),
        )
        classifier.fit(token_rows, token_labels)
        token_model_path = token_model_path.resolve()
        token_model_path.parent.mkdir(parents=True, exist_ok=True)
        dump(classifier, token_model_path)
        token_report.update(
            {
                "status": "trained",
                "token_model_path": str(token_model_path.relative_to(ROOT)).replace("\\", "/"),
                "label_counts": dict(Counter(token_labels)),
            }
        )

    model = {
        "schema_version": "0.1",
        "model_type": "hybrid_rule_plus_token_span_classifier",
        "status": "trained",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_policy": "Calibration splits only. Do not use held-out or external-reporting splits for model fitting.",
        "calibration_sources": source_reports,
        "field_cues": field_cues,
        "token_model_path": token_report.get("token_model_path"),
        "token_model_status": token_report["status"],
        "token_min_probability": token_min_probability,
        "token_category_min_probability": {
            "email": 0.999,
            "person_name": 0.999,
            "location": 0.999,
        },
    }
    report = {
        "rows_seen": rows_seen,
        "entities_seen": entities_seen,
        "mapped_cue_entities": mapped_entities,
        "categories": {category: sum(counts.values()) for category, counts in cue_counts.items()},
        "field_cue_count": sum(len(cues) for cues in field_cues.values()),
        "token_classifier": token_report,
        "calibration_sources": source_reports,
    }
    return model, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows-per-source", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--min-cue-count", type=int, default=2)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--token-model", default=str(DEFAULT_TOKEN_MODEL))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-o-multiplier", type=int, default=4)
    parser.add_argument("--token-min-probability", type=float, default=0.9)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    model, report = train_model(
        max_rows_per_source=args.max_rows_per_source,
        offset=args.offset,
        min_cue_count=args.min_cue_count,
        registry_path=pathlib.Path(args.registry),
        token_model_path=pathlib.Path(args.token_model),
        max_o_multiplier=args.max_o_multiplier,
        token_min_probability=args.token_min_probability,
    )
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = pathlib.Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"model": model, "report": report}, indent=2, sort_keys=True))
    else:
        print(
            "pass -- "
            f"rows={report['rows_seen']} entities={report['entities_seen']} "
            f"mapped_cues={report['mapped_cue_entities']} field_cues={report['field_cue_count']} "
            f"token_rows={report['token_classifier']['token_rows']} token_model={report['token_classifier']['status']} "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
