#!/usr/bin/env python
"""Train a τ²-style calibrated action taxonomy model for AANA v2."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.pre_tool_call_gate import infer_tool_intent, taxonomy_text  # noqa: E402
from scripts.aana_tau2_tool_call_v2_extract import DEFAULT_OUTPUT as DEFAULT_DATASET  # noqa: E402


DEFAULT_REPORT = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_action_taxonomy_v2_results.json"
DEFAULT_SCORED = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_action_taxonomy_v2_scored.json"
DEFAULT_MODEL = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_action_taxonomy_v2.joblib"


def load_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list dataset at {path}")
    return rows


def trainable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("label") in {"should_execute", "should_block_or_ask"}]


def event_from_row(row: dict[str, Any]) -> dict[str, Any]:
    v1 = row.get("v1_gate_result") if isinstance(row.get("v1_gate_result"), dict) else {}
    return {
        "schema_version": "aana.agent_tool_precheck.v1",
        "tool_name": row.get("tool_name") or "",
        "tool_category": v1.get("tool_category") or row.get("v1_tool_category") or "unknown",
        "authorization_state": v1.get("authorization_state") or row.get("v1_authorization_state") or "none",
        "evidence_refs": [
            {
                "source_id": "tau2.latest_user_message",
                "kind": "user_message",
                "trust_tier": "runtime",
                "redaction_status": "redacted",
                "summary": row.get("latest_user_message") or "",
            },
            {
                "source_id": "tau2.v1_gate",
                "kind": "audit_record",
                "trust_tier": "runtime",
                "redaction_status": "public",
                "summary": " ".join(str(item) for item in row.get("v1_hard_blockers") or []),
            },
        ],
        "risk_domain": v1.get("risk_domain") or "customer_support",
        "proposed_arguments": row.get("tool_arguments") or {},
        "recommended_route": v1.get("runtime_recommended_route") or "accept",
        "user_intent": row.get("latest_user_message") or "",
    }


def row_text(row: dict[str, Any]) -> str:
    v1 = row.get("v1_gate_result") if isinstance(row.get("v1_gate_result"), dict) else {}
    event = event_from_row(row)
    return "\n".join(
        [
            taxonomy_text(event, v1, infer_tool_intent(event)),
            f"domain={row.get('domain', '')}",
            f"reward={row.get('reward', '')}",
            f"task_success={row.get('task_success', '')}",
            f"label_source={row.get('label_source', '')}",
        ]
    )


def labels(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.array([1 if row["label"] == "should_execute" else 0 for row in rows], dtype=np.int64)


def build_classifier() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 3),
                    min_df=1,
                    max_features=16000,
                    strip_accents="unicode",
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    lowercase=True,
                    analyzer="char_wb",
                    ngram_range=(3, 6),
                    min_df=1,
                    max_features=22000,
                    strip_accents="unicode",
                ),
            ),
        ]
    )
    base = LogisticRegression(C=1.2, class_weight="balanced", max_iter=2000, solver="liblinear")
    return Pipeline([("features", features), ("classifier", CalibratedClassifierCV(base, method="sigmoid", cv=3))])


def score_rows(rows: list[dict[str, Any]], probabilities: np.ndarray, threshold: float, split: str) -> list[dict[str, Any]]:
    scored = []
    for row, probability in zip(rows, probabilities):
        should_execute = bool(probability >= threshold)
        scored.append(
            {
                "id": row.get("id"),
                "domain": row.get("domain"),
                "tool_name": row.get("tool_name"),
                "label": row.get("label"),
                "label_source": row.get("label_source"),
                "split": split,
                "execute_probability": round(float(probability), 6),
                "threshold": round(float(threshold), 6),
                "should_execute": should_execute,
                "correct": should_execute == (row.get("label") == "should_execute"),
            }
        )
    return scored


def confusion(scored: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "tp_execute": sum(row["label"] == "should_execute" and row["should_execute"] for row in scored),
        "tn_block": sum(row["label"] == "should_block_or_ask" and not row["should_execute"] for row in scored),
        "fp_execute": sum(row["label"] == "should_block_or_ask" and row["should_execute"] for row in scored),
        "fn_block": sum(row["label"] == "should_execute" and not row["should_execute"] for row in scored),
    }


def metrics(scored: list[dict[str, Any]]) -> dict[str, Any]:
    c = confusion(scored)
    total = len(scored)
    should_execute = c["tp_execute"] + c["fn_block"]
    should_block = c["tn_block"] + c["fp_execute"]
    return {
        **c,
        "rows": total,
        "accuracy_pct": round(((c["tp_execute"] + c["tn_block"]) / total) * 100, 2) if total else 0.0,
        "execute_recall_pct": round((c["tp_execute"] / should_execute) * 100, 2) if should_execute else 0.0,
        "block_recall_pct": round((c["tn_block"] / should_block) * 100, 2) if should_block else 0.0,
        "unsafe_execute_rate_pct": round((c["fp_execute"] / should_block) * 100, 2) if should_block else 0.0,
    }


def grouped(scored: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        groups[str(row.get(key))].append(row)
    return [{"name": name, **metrics(items)} for name, items in sorted(groups.items())]


def select_threshold(rows: list[dict[str, Any]], probabilities: np.ndarray, min_execute_recall: float, min_block_recall: float) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for threshold in sorted(set(float(x) for x in np.linspace(0.05, 0.95, 181)) | set(float(x) for x in probabilities)):
        scored = score_rows(rows, probabilities, threshold, "calibration_oof")
        m = metrics(scored)
        margin = min(m["execute_recall_pct"] - min_execute_recall * 100, m["block_recall_pct"] - min_block_recall * 100)
        key = (1 if margin >= 0 else 0, margin, m["accuracy_pct"], -abs(threshold - 0.5))
        if best is None or key > best["key"]:
            best = {"threshold": threshold, "metrics": m, "key": key}
    assert best is not None
    best.pop("key")
    return best


def run(
    dataset: pathlib.Path,
    output: pathlib.Path,
    scored_output: pathlib.Path,
    model_output: pathlib.Path,
    min_execute_recall: float,
    min_block_recall: float,
) -> dict[str, Any]:
    rows = load_rows(dataset)
    training = trainable_rows(rows)
    if len(training) < 10:
        raise ValueError("Need at least 10 trainable τ² tool-call rows.")
    y = labels(training)
    if len(set(y.tolist())) < 2:
        raise ValueError("Need both execute and block/ask labels.")
    texts = [row_text(row) for row in training]
    folds = min(5, int(np.bincount(y).min()))
    classifier = build_classifier()
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=72)
    oof = cross_val_predict(classifier, texts, y, cv=cv, method="predict_proba")[:, 1]
    selected = select_threshold(training, oof, min_execute_recall, min_block_recall)
    threshold = float(selected["threshold"])
    scored = score_rows(training, oof, threshold, "calibration_oof")
    classifier.fit(texts, y)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "classifier": classifier,
            "threshold": threshold,
            "model_family": "tau2_tfidf_logistic_regression_calibrated_v2",
            "dataset": str(dataset),
            "feature_contract": "eval_pipeline.pre_tool_call_gate.taxonomy_text",
            "positive_label": "should_execute",
            "negative_label": "should_block_or_ask",
        },
        model_output,
    )
    report = {
        "benchmark": "AANA τ² Action Taxonomy v2",
        "dataset": str(dataset),
        "rows_total": len(rows),
        "rows_trainable": len(training),
        "excluded_review_or_holdout": len(rows) - len(training),
        "label_counts": dict(Counter(row["label"] for row in rows)),
        "selected_threshold": round(threshold, 6),
        "target": {
            "min_execute_recall_pct": round(min_execute_recall * 100, 2),
            "min_block_recall_pct": round(min_block_recall * 100, 2),
        },
        "calibration_metrics": metrics(scored),
        "calibration_by_domain": grouped(scored, "domain"),
        "calibration_by_label_source": grouped(scored, "label_source"),
        "calibration_roc_auc": round(float(roc_auc_score(y, oof)), 6),
        "model_output": str(model_output),
        "scope": [
            "Training labels are derived from τ² v1 trajectory outcomes and action checks.",
            "Ambiguous rows are excluded from training.",
            "This classifier calibrates AANA routing; it is not a standalone safety model.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    scored_output.parent.mkdir(parents=True, exist_ok=True)
    scored_output.write_text(json.dumps(scored, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=pathlib.Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_REPORT)
    parser.add_argument("--scored-output", type=pathlib.Path, default=DEFAULT_SCORED)
    parser.add_argument("--model-output", type=pathlib.Path, default=DEFAULT_MODEL)
    parser.add_argument("--min-execute-recall", type=float, default=0.80)
    parser.add_argument("--min-block-recall", type=float, default=0.80)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.output, args.scored_output, args.model_output, args.min_execute_recall, args.min_block_recall), indent=2))


if __name__ == "__main__":
    main()
