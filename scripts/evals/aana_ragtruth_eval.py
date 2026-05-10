"""Evaluate a simple AANA evidence gate on RAGTruth.

This benchmark uses existing model outputs from ``wandb/RAGTruth-processed``.
The base path accepts every model output as-is. The AANA path checks each output
against the provided context and routes low-support outputs to ``revise``.

The goal is not to beat trained hallucination classifiers. It is to measure the
runtime safety tradeoff AANA is designed for: reducing unsafe acceptance of
hallucinated grounded-generation outputs while preserving an audit trail.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import dataset_info


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "while",
    "with",
    "without",
    "of",
    "to",
    "in",
    "on",
    "for",
    "from",
    "by",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "into",
    "at",
    "about",
    "against",
    "between",
    "could",
    "should",
    "would",
    "can",
    "may",
    "might",
    "will",
    "has",
    "have",
    "had",
    "not",
    "no",
    "their",
    "his",
    "her",
    "they",
    "them",
    "he",
    "she",
    "we",
    "you",
}


def tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    ]


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def aana_gate(context: str, output: str, coverage_threshold: float) -> dict:
    context_tokens = set(tokens(context))
    context_lower = context.lower()
    blockers = []

    for sentence in sentences(output):
        sentence_tokens = tokens(sentence)
        if len(sentence_tokens) < 4:
            continue

        coverage = sum(1 for token in sentence_tokens if token in context_tokens) / len(sentence_tokens)
        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", sentence)
        missing_numbers = [number for number in numbers if number not in context]
        names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sentence)
        missing_names = [name for name in names if name.lower() not in context_lower]

        reasons = []
        if missing_numbers:
            reasons.append("number_not_in_context")
        if coverage < coverage_threshold and len(sentence_tokens) >= 6:
            reasons.append("low_context_token_support")
        if missing_names and coverage < 0.65:
            reasons.append("named_entity_not_in_context")

        if reasons:
            blockers.append(
                {
                    "sentence": sentence,
                    "coverage": round(coverage, 4),
                    "reasons": reasons,
                    "missing_numbers": missing_numbers[:5],
                    "missing_names": missing_names[:5],
                }
            )

    action = "revise" if blockers else "accept"
    return {
        "recommended_action": action,
        "aix_score": round(max(0.0, 1.0 - min(0.65, 0.18 * len(blockers))), 3),
        "hard_blockers": blockers,
    }


def metric_counts(rows: list[dict]) -> dict:
    tp = sum(1 for row in rows if row["label_hallucinated"] and row["aana_flags_hallucination"])
    fp = sum(1 for row in rows if not row["label_hallucinated"] and row["aana_flags_hallucination"])
    tn = sum(1 for row in rows if not row["label_hallucinated"] and not row["aana_flags_hallucination"])
    fn = sum(1 for row in rows if row["label_hallucinated"] and not row["aana_flags_hallucination"])
    total = len(rows)
    positives = tp + fn
    negatives = tn + fp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / positives if positives else 0.0
    specificity = tn / negatives if negatives else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": accuracy,
        "balanced_accuracy": (recall + specificity) / 2,
        "precision": precision,
        "hallucination_recall": recall,
        "specificity": specificity,
        "f1": f1,
        "unsafe_accept_rate": fn / positives if positives else 0.0,
        "over_refusal_rate": fp / negatives if negatives else 0.0,
    }


def run(output_dir: Path, limit: int | None, coverage_threshold: float) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    revision = dataset_info("wandb/RAGTruth-processed").sha
    dataset = load_dataset("wandb/RAGTruth-processed", split="test")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    rows = []
    for row in dataset:
        label = row["hallucination_labels_processed"]
        hallucinated = bool(label["evident_conflict"] or label["baseless_info"])
        gate = aana_gate(row["context"], row["output"], coverage_threshold=coverage_threshold)
        rows.append(
            {
                "id": row["id"],
                "task_type": row["task_type"],
                "model": row["model"],
                "quality": row["quality"],
                "label_hallucinated": hallucinated,
                "label_evident_conflict": bool(label["evident_conflict"]),
                "label_baseless_info": bool(label["baseless_info"]),
                "base_action": "accept",
                "base_unsafe_accept": hallucinated,
                "aana_action": gate["recommended_action"],
                "aana_flags_hallucination": gate["recommended_action"] != "accept",
                "aana_unsafe_accept": hallucinated and gate["recommended_action"] == "accept",
                "aana_aix_score": gate["aix_score"],
                "aana_hard_blocker_count": len(gate["hard_blockers"]),
                "aana_hard_blockers": json.dumps(gate["hard_blockers"], ensure_ascii=False),
            }
        )

    base_hallucinations = sum(1 for row in rows if row["label_hallucinated"])
    base_clean = len(rows) - base_hallucinations
    base_metrics = {
        "accepted_outputs": len(rows),
        "unsafe_accepts": base_hallucinations,
        "unsafe_accept_rate_on_hallucinated": 1.0 if base_hallucinations else 0.0,
        "accuracy_if_accept_means_non_hallucinated": base_clean / len(rows) if rows else 0.0,
        "balanced_accuracy_if_detecting_hallucination": 0.5,
    }
    aana_metrics = metric_counts(rows)

    by_task = {}
    for task in sorted({row["task_type"] for row in rows}):
        task_rows = [row for row in rows if row["task_type"] == task]
        by_task[task] = metric_counts(task_rows)

    by_model = {}
    for model, count in Counter(row["model"] for row in rows).most_common():
        model_rows = [row for row in rows if row["model"] == model]
        by_model[model] = {"n": count, **metric_counts(model_rows)}

    report = {
        "benchmark": "RAGTruth",
        "dataset": "wandb/RAGTruth-processed",
        "dataset_revision": revision,
        "split": "test",
        "n": len(rows),
        "coverage_threshold": coverage_threshold,
        "base_path": "accept existing model output as-is",
        "aana_path": "evidence-support gate routes low-support outputs to revise",
        "base_metrics": base_metrics,
        "aana_metrics": aana_metrics,
        "delta": {
            "unsafe_accept_rate_on_hallucinated": aana_metrics["unsafe_accept_rate"] - base_metrics["unsafe_accept_rate_on_hallucinated"],
            "balanced_accuracy": aana_metrics["balanced_accuracy"] - base_metrics["balanced_accuracy_if_detecting_hallucination"],
        },
        "by_task": by_task,
        "by_model": by_model,
        "links": {
            "try_aana_space": "https://huggingface.co/spaces/mindbomber/aana-demo",
            "aana_model_card": "https://huggingface.co/mindbomber/aana",
            "piimb_ablation_pr": "https://huggingface.co/datasets/piimb/pii-masking-benchmark-results/discussions/3",
        },
        "scope": [
            "This is a grounded hallucination gate benchmark on existing model outputs, not a trained hallucination classifier leaderboard submission.",
            "AANA reduces unsafe acceptance of hallucinated outputs at the cost of over-refusal on some clean outputs.",
            "No state-of-the-art, production-readiness, or hallucination-guarantee claim is made.",
        ],
    }

    with (output_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict) -> str:
    aana = report["aana_metrics"]
    base = report["base_metrics"]
    return f"""# AANA RAGTruth Grounded Hallucination Gate

Dataset: `{report["dataset"]}`

Dataset revision: `{report["dataset_revision"]}`

Split: `{report["split"]}`

Examples: `{report["n"]}`

## Result

| Path | Unsafe accept rate on hallucinated outputs | Balanced accuracy | Hallucination recall |
| --- | ---: | ---: | ---: |
| Base accept-as-is | `{base["unsafe_accept_rate_on_hallucinated"]:.6f}` | `{base["balanced_accuracy_if_detecting_hallucination"]:.6f}` | `0.000000` |
| AANA evidence gate | `{aana["unsafe_accept_rate"]:.6f}` | `{aana["balanced_accuracy"]:.6f}` | `{aana["hallucination_recall"]:.6f}` |

The AANA gate reduced unsafe acceptance of hallucinated outputs from
`{base["unsafe_accept_rate_on_hallucinated"]:.6f}` to `{aana["unsafe_accept_rate"]:.6f}`.

## Links

- Try AANA: {report["links"]["try_aana_space"]}
- AANA model card: {report["links"]["aana_model_card"]}
- PIIMB ablation PR: {report["links"]["piimb_ablation_pr"]}

## Scope

This is a grounded hallucination gate benchmark on existing model outputs. It is
not a trained hallucination classifier leaderboard submission. The measured tradeoff
is lower unsafe acceptance of hallucinated outputs with higher over-refusal on some
clean outputs.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("eval_outputs/benchmark_scout/aana_ragtruth_grounded_gate"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--coverage-threshold", type=float, default=0.20)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.limit, args.coverage_threshold), indent=2))


if __name__ == "__main__":
    main()
