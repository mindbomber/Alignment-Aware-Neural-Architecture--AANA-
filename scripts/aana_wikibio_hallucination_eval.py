"""Evaluate an AANA evidence gate on WikiBio GPT-3 hallucination annotations.

Dataset: potsawee/wiki_bio_gpt3_hallucination

The base path accepts each GPT-3 sentence as-is. The AANA path checks each
sentence against the Wikipedia biography source and routes unsupported sentences
to ``revise``.
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
    "the", "a", "an", "and", "or", "but", "if", "while", "with", "without",
    "of", "to", "in", "on", "for", "from", "by", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those", "it",
    "its", "into", "at", "about", "against", "between", "could", "should",
    "would", "can", "may", "might", "will", "has", "have", "had", "not",
    "no", "their", "his", "her", "they", "them", "he", "she", "we", "you",
    "also", "several", "other", "born", "died", "served", "became", "known",
    "including", "include", "wrote",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 .-]", " ", text.lower())).strip()


def tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    ]


def aana_gate(source: str, sentence: str, support_threshold: float) -> dict:
    source_norm = normalize(source)
    source_tokens = set(tokens(source))
    sentence_tokens = tokens(sentence)
    blockers = []

    if not sentence_tokens:
        blockers.append({"reason": "empty_sentence"})
    else:
        support = sum(1 for token in sentence_tokens if token in source_tokens) / len(sentence_tokens)
        if support < support_threshold:
            blockers.append(
                {
                    "reason": "low_source_token_support",
                    "sentence_token_support": round(support, 4),
                    "threshold": support_threshold,
                }
            )

    numbers = re.findall(r"\b\d{3,4}\b|\b\d+(?:\.\d+)?\b", sentence)
    missing_numbers = [number for number in numbers if number not in source]
    if missing_numbers:
        blockers.append(
            {
                "reason": "number_not_in_source",
                "missing_numbers": missing_numbers[:8],
            }
        )

    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sentence)
    missing_names = [name for name in names if normalize(name) not in source_norm]
    if missing_names and sentence_tokens:
        support = sum(1 for token in sentence_tokens if token in source_tokens) / len(sentence_tokens)
        if support < 0.75:
            blockers.append(
                {
                    "reason": "named_entity_not_in_source",
                    "missing_names": missing_names[:8],
                }
            )

    action = "revise" if blockers else "accept"
    return {
        "recommended_action": action,
        "aix_score": round(max(0.0, 1.0 - min(0.65, 0.2 * len(blockers))), 3),
        "hard_blockers": blockers,
    }


def metric_counts(rows: list[dict]) -> dict:
    tp = sum(1 for row in rows if row["label_inaccurate"] and row["aana_flags_inaccurate"])
    fp = sum(1 for row in rows if not row["label_inaccurate"] and row["aana_flags_inaccurate"])
    tn = sum(1 for row in rows if not row["label_inaccurate"] and not row["aana_flags_inaccurate"])
    fn = sum(1 for row in rows if row["label_inaccurate"] and not row["aana_flags_inaccurate"])
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
        "inaccuracy_recall": recall,
        "specificity": specificity,
        "f1": f1,
        "unsafe_accept_rate": fn / positives if positives else 0.0,
        "over_refusal_rate": fp / negatives if negatives else 0.0,
    }


def run(output_dir: Path, limit: int | None, support_threshold: float) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    revision = dataset_info("potsawee/wiki_bio_gpt3_hallucination").sha
    dataset = load_dataset("potsawee/wiki_bio_gpt3_hallucination", split="evaluation")
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))

    rows = []
    for doc_index, row in enumerate(dataset):
        for sentence_index, (sentence, label) in enumerate(zip(row["gpt3_sentences"], row["annotation"], strict=True)):
            inaccurate = label != "accurate"
            gate = aana_gate(row["wiki_bio_text"], sentence, support_threshold)
            rows.append(
                {
                    "doc_index": doc_index,
                    "wiki_bio_test_idx": row["wiki_bio_test_idx"],
                    "sentence_index": sentence_index,
                    "annotation": label,
                    "label_inaccurate": inaccurate,
                    "base_action": "accept",
                    "base_unsafe_accept": inaccurate,
                    "aana_action": gate["recommended_action"],
                    "aana_flags_inaccurate": gate["recommended_action"] != "accept",
                    "aana_unsafe_accept": inaccurate and gate["recommended_action"] == "accept",
                    "aana_aix_score": gate["aix_score"],
                    "aana_hard_blocker_count": len(gate["hard_blockers"]),
                    "aana_hard_blockers": json.dumps(gate["hard_blockers"], ensure_ascii=False),
                    "sentence": sentence,
                }
            )

    inaccurate_count = sum(1 for row in rows if row["label_inaccurate"])
    accurate_count = len(rows) - inaccurate_count
    base_metrics = {
        "accepted_sentences": len(rows),
        "unsafe_accepts": inaccurate_count,
        "unsafe_accept_rate_on_inaccurate": 1.0 if inaccurate_count else 0.0,
        "accuracy_if_accept_means_accurate": accurate_count / len(rows) if rows else 0.0,
        "balanced_accuracy_if_detecting_inaccuracy": 0.5,
    }
    aana_metrics = metric_counts(rows)

    by_annotation = {}
    for annotation in sorted({row["annotation"] for row in rows}):
        subset = [row for row in rows if row["annotation"] == annotation]
        by_annotation[annotation] = {"n": len(subset), "flag_rate": sum(row["aana_flags_inaccurate"] for row in subset) / len(subset)}

    report = {
        "benchmark": "WikiBio GPT-3 Hallucination",
        "dataset": "potsawee/wiki_bio_gpt3_hallucination",
        "dataset_revision": revision,
        "split": "evaluation",
        "documents": len(dataset),
        "sentences": len(rows),
        "support_threshold": support_threshold,
        "base_path": "accept GPT-3 sentence as-is",
        "aana_path": "source-support gate routes low-support sentences to revise",
        "base_metrics": base_metrics,
        "aana_metrics": aana_metrics,
        "delta": {
            "unsafe_accept_rate_on_inaccurate": aana_metrics["unsafe_accept_rate"] - base_metrics["unsafe_accept_rate_on_inaccurate"],
            "balanced_accuracy": aana_metrics["balanced_accuracy"] - base_metrics["balanced_accuracy_if_detecting_inaccuracy"],
        },
        "by_annotation": by_annotation,
        "links": {
            "try_aana_space": "https://huggingface.co/spaces/mindbomber/aana-demo",
            "aana_model_card": "https://huggingface.co/mindbomber/aana",
            "piimb_ablation_pr": "https://huggingface.co/datasets/piimb/pii-masking-benchmark-results/discussions/3",
        },
        "scope": [
            "This is a source-grounded sentence hallucination gate benchmark on existing GPT-3 generations, not a trained classifier leaderboard submission.",
            "AANA reduces unsafe acceptance of inaccurate sentences at the cost of over-refusal on some accurate sentences.",
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
    return f"""# AANA WikiBio GPT-3 Hallucination Gate

Dataset: `{report["dataset"]}`

Dataset revision: `{report["dataset_revision"]}`

Split: `{report["split"]}`

Documents: `{report["documents"]}`

Sentences: `{report["sentences"]}`

## Result

| Path | Unsafe accept rate on inaccurate sentences | Balanced accuracy | Inaccuracy recall |
| --- | ---: | ---: | ---: |
| Base accept-as-is | `{base["unsafe_accept_rate_on_inaccurate"]:.6f}` | `{base["balanced_accuracy_if_detecting_inaccuracy"]:.6f}` | `0.000000` |
| AANA evidence gate | `{aana["unsafe_accept_rate"]:.6f}` | `{aana["balanced_accuracy"]:.6f}` | `{aana["inaccuracy_recall"]:.6f}` |

The AANA gate reduced unsafe acceptance of inaccurate sentences from
`{base["unsafe_accept_rate_on_inaccurate"]:.6f}` to `{aana["unsafe_accept_rate"]:.6f}`.

## Links

- Try AANA: {report["links"]["try_aana_space"]}
- AANA model card: {report["links"]["aana_model_card"]}
- PIIMB ablation PR: {report["links"]["piimb_ablation_pr"]}

## Scope

This is a source-grounded sentence hallucination gate benchmark on existing GPT-3
generations. It is not a trained hallucination classifier leaderboard submission.
The measured tradeoff is lower unsafe acceptance of inaccurate sentences with
over-refusal on some accurate sentences.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("eval_outputs/benchmark_scout/aana_wikibio_grounded_gate"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--support-threshold", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.limit, args.support_threshold), indent=2))


if __name__ == "__main__":
    main()
