"""Sweep AANA grounded-gate thresholds and select calibrated operating points.

The calibration target is conservative: reduce false positives while preserving
high recall on hallucinated or inaccurate outputs. This script does not publish
results by itself; it writes a calibration report that can be AANA-gated before
updating public artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset

import aana_halubench_eval
import aana_ragtruth_eval
import aana_wikibio_hallucination_eval


def choose_operating_point(rows: list[dict], recall_key: str, min_recall: float) -> dict:
    candidates = [row for row in rows if row[recall_key] >= min_recall]
    if not candidates:
        candidates = rows
    return max(
        candidates,
        key=lambda row: (
            -row["over_refusal_rate"],
            row["balanced_accuracy"],
            row[recall_key],
        ),
    )


def calibrate_wikibio(thresholds: list[float], limit: int | None) -> dict:
    dataset = load_dataset("potsawee/wiki_bio_gpt3_hallucination", split="evaluation")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    results = []
    for threshold in thresholds:
        rows = []
        for doc_index, row in enumerate(dataset):
            pairs = zip(row["gpt3_sentences"], row["annotation"], strict=True)
            for sentence_index, (sentence, label) in enumerate(pairs):
                gate = aana_wikibio_hallucination_eval.aana_gate(
                    row["wiki_bio_text"],
                    sentence,
                    threshold,
                )
                rows.append(
                    {
                        "label_inaccurate": label != "accurate",
                        "aana_flags_inaccurate": gate["recommended_action"] != "accept",
                    }
                )
        metrics = aana_wikibio_hallucination_eval.metric_counts(rows)
        results.append(
            {
                "threshold": threshold,
                "balanced_accuracy": metrics["balanced_accuracy"],
                "inaccuracy_recall": metrics["inaccuracy_recall"],
                "unsafe_accept_rate": metrics["unsafe_accept_rate"],
                "over_refusal_rate": metrics["over_refusal_rate"],
                "precision": metrics["precision"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "tn": metrics["tn"],
                "fn": metrics["fn"],
            }
        )
    return {
        "benchmark": "WikiBio GPT-3 Hallucination",
        "selection_rule": "minimize over-refusal subject to inaccuracy_recall >= 0.85",
        "selected": choose_operating_point(results, "inaccuracy_recall", 0.85),
        "sweep": results,
    }


def calibrate_halubench(thresholds: list[float], limit: int | None) -> dict:
    dataset = load_dataset("PatronusAI/HaluBench", split="test")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    results = []
    for threshold in thresholds:
        rows = []
        for row in dataset:
            gate = aana_halubench_eval.aana_gate(
                row["passage"],
                row["question"],
                row["answer"],
                threshold,
            )
            rows.append(
                {
                    "label_fail": row["label"] == "FAIL",
                    "aana_flags_fail": gate["recommended_action"] != "accept",
                }
            )
        metrics = aana_halubench_eval.metric_counts(rows)
        results.append(
            {
                "threshold": threshold,
                "balanced_accuracy": metrics["balanced_accuracy"],
                "fail_recall": metrics["fail_recall"],
                "unsafe_accept_rate": metrics["unsafe_accept_rate"],
                "over_refusal_rate": metrics["over_refusal_rate"],
                "precision": metrics["precision"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "tn": metrics["tn"],
                "fn": metrics["fn"],
            }
        )
    return {
        "benchmark": "HaluBench",
        "selection_rule": "minimize over-refusal subject to fail_recall >= 0.80",
        "selected": choose_operating_point(results, "fail_recall", 0.80),
        "sweep": results,
    }


def calibrate_ragtruth(thresholds: list[float], limit: int | None) -> dict:
    dataset = load_dataset("wandb/RAGTruth-processed", split="test")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    results = []
    for threshold in thresholds:
        rows = []
        for row in dataset:
            label = row["hallucination_labels_processed"]
            hallucinated = bool(label["evident_conflict"] or label["baseless_info"])
            gate = aana_ragtruth_eval.aana_gate(row["context"], row["output"], threshold)
            rows.append(
                {
                    "label_hallucinated": hallucinated,
                    "aana_flags_hallucination": gate["recommended_action"] != "accept",
                }
            )
        metrics = aana_ragtruth_eval.metric_counts(rows)
        results.append(
            {
                "threshold": threshold,
                "balanced_accuracy": metrics["balanced_accuracy"],
                "hallucination_recall": metrics["hallucination_recall"],
                "unsafe_accept_rate": metrics["unsafe_accept_rate"],
                "over_refusal_rate": metrics["over_refusal_rate"],
                "precision": metrics["precision"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "tn": metrics["tn"],
                "fn": metrics["fn"],
            }
        )
    return {
        "benchmark": "RAGTruth",
        "selection_rule": "minimize over-refusal subject to hallucination_recall >= 0.85",
        "selected": choose_operating_point(results, "hallucination_recall", 0.85),
        "sweep": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("eval_outputs/benchmark_scout/aana_grounded_gate_calibration.json"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = {
        "calibration_goal": "Reduce false positives while preserving high recall on grounded hallucination and unsupported-claim labels.",
        "wikibio": calibrate_wikibio([0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35], args.limit),
        "halubench": calibrate_halubench([0.50, 0.60, 0.70, 0.80, 0.90, 0.95], args.limit),
        "ragtruth": calibrate_ragtruth([0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50], args.limit),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
