#!/usr/bin/env python
"""Analyze high-risk PII category performance from a privacy HF experiment artifact."""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter, defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "eval_outputs" / "privacy_pii_hf_experiment_live_300_v2_calibrated.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "privacy_pii_high_risk_category_report.json"
HIGH_RISK_CATEGORIES = {
    "account_number",
    "bank_routing_number",
    "credit_card",
    "iban",
    "national_id",
    "passport",
    "ssn",
}

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
        "social security",
        "social insurance",
        "tax number",
        "tax id",
        "assurance sociale",
        "segurança social",
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
        "sistemul intern",
        "codul",
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
}


def _safe_preview(row: dict[str, Any], limit: int = 260) -> str:
    preview = str(row.get("redacted_preview") or "")
    return preview[:limit] + ("..." if len(preview) > limit else "")


def _cluster_names(row: dict[str, Any]) -> list[str]:
    preview = str(row.get("redacted_preview") or "").lower()
    names = [name for name, cues in CONTEXT_CLUSTERS.items() if any(cue in preview for cue in cues)]
    return names or ["unclustered"]


def analyze(payload: dict[str, Any], max_examples: int) -> dict[str, Any]:
    by_category: dict[str, Counter] = {category: Counter() for category in sorted(HIGH_RISK_CATEGORIES)}
    miss_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    false_positive_examples: list[dict[str, Any]] = []
    route_mismatches = Counter()

    for row in payload.get("rows", []):
        expected = set(row.get("expected_categories") or [])
        detected = set(row.get("detected_categories") or [])
        high_expected = expected & HIGH_RISK_CATEGORIES
        high_detected = detected & HIGH_RISK_CATEGORIES

        for category in sorted(HIGH_RISK_CATEGORIES):
            if category in high_expected:
                by_category[category]["expected"] += 1
                if category in detected:
                    by_category[category]["detected"] += 1
                else:
                    by_category[category]["missed"] += 1
                    if len(miss_examples[category]) < max_examples:
                        miss_examples[category].append(
                            {
                                "id": row.get("id"),
                                "source_dataset": row.get("source_dataset"),
                                "language": row.get("language"),
                                "expected_route": row.get("expected_route"),
                                "actual_route": row.get("actual_route"),
                                "detected_categories": sorted(detected),
                                "context_clusters": _cluster_names(row),
                                "redacted_preview": _safe_preview(row),
                            }
                        )
            elif category in high_detected:
                by_category[category]["unexpected_detected"] += 1

        if row.get("expected_route") != row.get("actual_route"):
            route_mismatches[(row.get("expected_route"), row.get("actual_route"))] += 1

        if not row.get("contains_pii") and detected:
            false_positive_examples.append(
                {
                    "id": row.get("id"),
                    "source_dataset": row.get("source_dataset"),
                    "language": row.get("language"),
                    "detected_categories": sorted(detected),
                    "redacted_preview": _safe_preview(row),
                }
            )

    category_metrics = {}
    for category, counts in by_category.items():
        expected = counts["expected"]
        detected = counts["detected"]
        category_metrics[category] = {
            "expected": expected,
            "detected": detected,
            "missed": counts["missed"],
            "unexpected_detected": counts["unexpected_detected"],
            "recall": detected / expected if expected else None,
        }

    ranked_gaps = sorted(
        [
            {
                "category": category,
                "missed": metrics["missed"],
                "expected": metrics["expected"],
                "recall": metrics["recall"],
            }
            for category, metrics in category_metrics.items()
            if metrics["expected"]
        ],
        key=lambda item: (-int(item["missed"]), float(item["recall"] or 0.0)),
    )
    miss_context_clusters = {
        category: dict(Counter(cluster for row in payload.get("rows", []) if category in set(row.get("expected_categories") or []) and category not in set(row.get("detected_categories") or []) for cluster in _cluster_names(row)))
        for category in sorted(HIGH_RISK_CATEGORIES)
    }

    return {
        "source_artifact": payload.get("experiment_id"),
        "mode": payload.get("mode"),
        "detector_version": payload.get("detector_version"),
        "case_count": payload.get("metrics", {}).get("case_count"),
        "overall_metrics": payload.get("metrics", {}),
        "high_risk_category_metrics": category_metrics,
        "ranked_high_risk_gaps": ranked_gaps,
        "route_mismatches": {f"{expected}->{actual}": count for (expected, actual), count in route_mismatches.items()},
        "false_positive_count": len(false_positive_examples),
        "false_positive_examples": false_positive_examples[:max_examples],
        "miss_context_clusters": miss_context_clusters,
        "miss_examples": dict(miss_examples),
        "next_target": ranked_gaps[0]["category"] if ranked_gaps else None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    input_path = pathlib.Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    report = analyze(payload, max_examples=args.max_examples)
    report["input_artifact"] = str(input_path.relative_to(ROOT)).replace("\\", "/") if input_path.is_absolute() and input_path.is_relative_to(ROOT) else str(input_path)

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "pass -- "
            f"cases={report['case_count']} next_target={report['next_target']} "
            f"false_positives={report['false_positive_count']} output={output_path}"
        )
        for item in report["ranked_high_risk_gaps"]:
            recall = item["recall"]
            recall_text = "n/a" if recall is None else f"{recall:.3f}"
            print(
                f"- {item['category']}: recall={recall_text} "
                f"missed={item['missed']} expected={item['expected']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
