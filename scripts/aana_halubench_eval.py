"""Evaluate a simple AANA evidence gate on HaluBench.

HaluBench contains passages, questions, candidate answers, and PASS/FAIL labels.
The base path accepts every candidate answer as-is. The AANA path checks whether
the answer is grounded in the passage and routes low-support answers to
``revise``.

This measures a runtime gate tradeoff, not a trained hallucination classifier.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from collections import Counter
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import dataset_info


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "while", "with", "without",
    "of", "to", "in", "on", "for", "from", "by", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those", "it",
    "its", "into", "at", "about", "against", "between", "could", "should",
    "would", "can", "may", "might", "will", "has", "have", "had", "not",
    "no", "their", "his", "her", "they", "them", "he", "she", "we", "you",
    "how", "many", "which", "what", "when", "where", "who", "why", "did",
    "do", "does", "long", "scored", "percent",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.% -]", " ", text.lower())).strip()


def tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+(?:\.[0-9]+)?", text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def parse_answer(answer: str) -> list[str]:
    try:
        value = ast.literal_eval(answer)
    except Exception:
        return [answer]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [answer]


def aana_gate(passage: str, question: str, answer: str, support_threshold: float) -> dict:
    passage_norm = normalize(passage)
    passage_tokens = set(tokens(passage))
    answer_tokens = tokens(answer)
    answer_parts = parse_answer(answer)
    blockers = []

    for part in answer_parts:
        part_norm = normalize(part)
        if not part_norm or part_norm in passage_norm:
            continue
        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", part)
        missing_numbers = [number for number in numbers if number not in passage]
        if missing_numbers:
            blockers.append(
                {
                    "reason": "number_not_in_passage",
                    "answer_part": part,
                    "missing_numbers": missing_numbers[:5],
                }
            )

    if not answer_tokens:
        blockers.append({"reason": "empty_answer"})
    else:
        support = sum(1 for token in answer_tokens if token in passage_tokens) / len(answer_tokens)
        if support < support_threshold:
            blockers.append(
                {
                    "reason": "low_answer_token_support",
                    "answer_token_support": round(support, 4),
                    "threshold": support_threshold,
                }
            )

    if len(answer_parts) > 1:
        missing_parts = [part for part in answer_parts if normalize(part) not in passage_norm]
        if len(missing_parts) / max(1, len(answer_parts)) > 0.4:
            blockers.append(
                {
                    "reason": "list_items_not_grounded_verbatim",
                    "missing_parts": missing_parts[:5],
                }
            )

    action = "revise" if blockers else "accept"
    return {
        "recommended_action": action,
        "aix_score": round(max(0.0, 1.0 - min(0.65, 0.2 * len(blockers))), 3),
        "hard_blockers": blockers,
    }


def metric_counts(rows: list[dict]) -> dict:
    tp = sum(1 for row in rows if row["label_fail"] and row["aana_flags_fail"])
    fp = sum(1 for row in rows if not row["label_fail"] and row["aana_flags_fail"])
    tn = sum(1 for row in rows if not row["label_fail"] and not row["aana_flags_fail"])
    fn = sum(1 for row in rows if row["label_fail"] and not row["aana_flags_fail"])
    positives = tp + fn
    negatives = tn + fp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / positives if positives else 0.0
    specificity = tn / negatives if negatives else 0.0
    accuracy = (tp + tn) / len(rows) if rows else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": accuracy,
        "balanced_accuracy": (recall + specificity) / 2,
        "precision": precision,
        "fail_recall": recall,
        "specificity": specificity,
        "f1": f1,
        "unsafe_accept_rate": fn / positives if positives else 0.0,
        "over_refusal_rate": fp / negatives if negatives else 0.0,
    }


def run(output_dir: Path, limit: int | None, support_threshold: float) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    revision = dataset_info("PatronusAI/HaluBench").sha
    dataset = load_dataset("PatronusAI/HaluBench", split="test")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    rows = []
    for row in dataset:
        label_fail = row["label"] == "FAIL"
        gate = aana_gate(row["passage"], row["question"], row["answer"], support_threshold)
        rows.append(
            {
                "id": row["id"],
                "source_ds": row["source_ds"],
                "label": row["label"],
                "label_fail": label_fail,
                "base_action": "accept",
                "base_unsafe_accept": label_fail,
                "aana_action": gate["recommended_action"],
                "aana_flags_fail": gate["recommended_action"] != "accept",
                "aana_unsafe_accept": label_fail and gate["recommended_action"] == "accept",
                "aana_aix_score": gate["aix_score"],
                "aana_hard_blocker_count": len(gate["hard_blockers"]),
                "aana_hard_blockers": json.dumps(gate["hard_blockers"], ensure_ascii=False),
            }
        )

    fail_count = sum(1 for row in rows if row["label_fail"])
    pass_count = len(rows) - fail_count
    base_metrics = {
        "accepted_outputs": len(rows),
        "unsafe_accepts": fail_count,
        "unsafe_accept_rate_on_fail": 1.0 if fail_count else 0.0,
        "accuracy_if_accept_means_pass": pass_count / len(rows) if rows else 0.0,
        "balanced_accuracy_if_detecting_fail": 0.5,
    }
    aana_metrics = metric_counts(rows)

    by_source = {}
    for source in sorted({row["source_ds"] for row in rows}):
        source_rows = [row for row in rows if row["source_ds"] == source]
        by_source[source] = {"n": len(source_rows), **metric_counts(source_rows)}

    report = {
        "benchmark": "HaluBench",
        "dataset": "PatronusAI/HaluBench",
        "dataset_revision": revision,
        "split": "test",
        "n": len(rows),
        "support_threshold": support_threshold,
        "base_path": "accept candidate answer as-is",
        "aana_path": "evidence-support gate routes low-support answers to revise",
        "base_metrics": base_metrics,
        "aana_metrics": aana_metrics,
        "delta": {
            "unsafe_accept_rate_on_fail": aana_metrics["unsafe_accept_rate"] - base_metrics["unsafe_accept_rate_on_fail"],
            "balanced_accuracy": aana_metrics["balanced_accuracy"] - base_metrics["balanced_accuracy_if_detecting_fail"],
        },
        "by_source": by_source,
        "links": {
            "try_aana_space": "https://huggingface.co/spaces/mindbomber/aana-demo",
            "aana_model_card": "https://huggingface.co/mindbomber/aana",
            "piimb_ablation_pr": "https://huggingface.co/datasets/piimb/pii-masking-benchmark-results/discussions/3",
        },
        "scope": [
            "This is a grounded QA hallucination gate benchmark on existing candidate answers, not a trained classifier leaderboard submission.",
            "AANA reduces unsafe acceptance of FAIL answers at the cost of over-refusal on some PASS answers.",
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
    base = report["base_metrics"]
    aana = report["aana_metrics"]
    return f"""# AANA HaluBench Grounded QA Gate

Dataset: `{report["dataset"]}`

Dataset revision: `{report["dataset_revision"]}`

Split: `{report["split"]}`

Examples: `{report["n"]}`

## Result

| Path | Unsafe accept rate on FAIL answers | Balanced accuracy | FAIL recall |
| --- | ---: | ---: | ---: |
| Base accept-as-is | `{base["unsafe_accept_rate_on_fail"]:.6f}` | `{base["balanced_accuracy_if_detecting_fail"]:.6f}` | `0.000000` |
| AANA evidence gate | `{aana["unsafe_accept_rate"]:.6f}` | `{aana["balanced_accuracy"]:.6f}` | `{aana["fail_recall"]:.6f}` |

The AANA gate reduced unsafe acceptance of FAIL answers from
`{base["unsafe_accept_rate_on_fail"]:.6f}` to `{aana["unsafe_accept_rate"]:.6f}`.

## Links

- Try AANA: {report["links"]["try_aana_space"]}
- AANA model card: {report["links"]["aana_model_card"]}
- PIIMB ablation PR: {report["links"]["piimb_ablation_pr"]}

## Scope

This is a grounded QA hallucination gate benchmark on existing candidate answers.
It is not a trained hallucination classifier leaderboard submission. The measured
tradeoff is lower unsafe acceptance of FAIL answers with over-refusal on some PASS
answers.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("eval_outputs/benchmark_scout/aana_halubench_grounded_gate"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--support-threshold", type=float, default=0.90)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.limit, args.support_threshold), indent=2))


if __name__ == "__main__":
    main()
