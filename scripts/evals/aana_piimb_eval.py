"""Run an AANA privacy-gate baseline on the PIIMB benchmark.

The PIIMB leaderboard ranks PII masking systems with character-level masking F2.
This runner uses PIIMB's official dataset, schemas, and metric implementation,
but replaces the model pipeline with an explicit AANA-style verifier stack:
deterministic evidence detectors, offset validation, span merge correction, and
a publish gate that writes PIIMB-compatible result files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import dataset_info


ROOT = Path(__file__).resolve().parents[2]
PIIMB_SRC = ROOT / "eval_outputs" / "benchmark_scout" / "repos" / "pii-masking-benchmark" / "src"
if str(PIIMB_SRC) not in sys.path:
    sys.path.insert(0, str(PIIMB_SRC))

from piimb.metrics import compute_metrics  # noqa: E402
from piimb.models import (  # noqa: E402
    DATASET_ID,
    Entity,
    ModelMetadata,
    PipelineType,
    ScoreResult,
    SourceDataset,
    Subset,
    TaskResults,
)


MODEL_ID = "mindbomber/aana-piimb-policy-baseline"
MODEL_DIR = "mindbomber__aana-piimb-policy-baseline__policy-v1"


@dataclass(frozen=True)
class Detector:
    label: str
    pattern: re.Pattern[str]


DETECTORS = [
    Detector("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    Detector("URL", re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]{}\"']+", re.IGNORECASE)),
    Detector("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    Detector("IP_ADDRESS", re.compile(r"\b(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{1,4}\b", re.IGNORECASE)),
    Detector("MAC_ADDRESS", re.compile(r"\b[0-9A-F]{2}(?::[0-9A-F]{2}){5}\b", re.IGNORECASE)),
    Detector("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    Detector("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    Detector("IBAN_CODE", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    Detector("DATE_TIME", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    Detector("DATE_TIME", re.compile(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b")),
    Detector(
        "DATE_TIME",
        re.compile(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
            r"\s+\d{1,2}(?:,\s*\d{2,4})?\b",
            re.IGNORECASE,
        ),
    ),
    Detector("DATE_TIME", re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b", re.IGNORECASE)),
    Detector(
        "PHONE_NUMBER",
        re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.\-()]*)?(?:\(?\d{2,4}\)?[\s.\-]*){2,4}\d{2,4}(?!\w)"),
    ),
    Detector("ZIPCODE", re.compile(r"\b\d{5}(?:-\d{4})?\b")),
    Detector("COORDINATE", re.compile(r"\b-?\d{1,3}\.\d{3,},\s*-?\d{1,3}\.\d{3,}\b")),
    Detector("UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.IGNORECASE)),
    Detector(
        "SECRET",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|token|password|passwd|pwd|secret|pin|cvv)\b"
            r"\s*(?:is|=|:)?\s*['\"]?([A-Za-z0-9_./+=@!#$%^&*?~-]{4,})"
        ),
    ),
    Detector(
        "STREET_ADDRESS",
        re.compile(
            r"\b\d{1,6}\s+[A-Z][A-Za-z0-9.'-]*(?:\s+[A-Z][A-Za-z0-9.'-]*){0,4}\s+"
            r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Court|Ct)\b",
            re.IGNORECASE,
        ),
    ),
    Detector(
        "PERSON",
        re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"),
    ),
]


def _valid_credit_like(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return 13 <= len(digits) <= 19 and len(set(digits)) > 1


def _detected_spans(text: str) -> list[Entity]:
    entities: list[Entity] = []
    for detector in DETECTORS:
        for match in detector.pattern.finditer(text):
            if detector.label == "SECRET" and match.lastindex:
                start, end = match.span(1)
            else:
                start, end = match.span()

            span = text[start:end].strip(" ,.;:)]}\"'")
            start += len(text[start:end]) - len(text[start:end].lstrip(" ,.;:)]}\"'"))
            end = start + len(span)
            if start >= end:
                continue
            if detector.label == "CREDIT_CARD" and not _valid_credit_like(span):
                continue
            entities.append(Entity(start=start, end=end, label=detector.label))

    return _merge_entities(entities)


def _merge_entities(entities: list[Entity]) -> list[Entity]:
    if not entities:
        return []
    ordered = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))
    merged: list[Entity] = []
    for entity in ordered:
        if not merged or entity.start > merged[-1].end:
            merged.append(entity)
            continue
        last = merged[-1]
        if entity.end > last.end:
            merged[-1] = Entity(start=last.start, end=entity.end, label=last.label)
    return merged


def _metadata() -> ModelMetadata:
    return ModelMetadata(
        name=MODEL_ID,
        pipeline_type=PipelineType.TOKEN_CLASSIFICATION,
        model_type="aana-policy-baseline",
        revision="policy-v1",
        dtype="policy-v1",
        release_date="2026-05-07",
        languages=["en", "multilingual-patterns"],
        datasets=[],
        base_model=[],
        license="MIT",
        n_parameters=0,
        n_embedding_parameters=0,
        n_active_parameters=0,
        max_tokens=None,
        threshold=None,
        reference=f"https://huggingface.co/{MODEL_ID}",
    )


def _source_filename(source_dataset: str) -> str:
    return source_dataset.replace("/", "__") + ".json"


def run(output_dir: Path, max_samples: int | None) -> dict[str, float]:
    revision = dataset_info(repo_id=DATASET_ID).sha
    result_dir = output_dir / MODEL_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    ds = load_dataset(path=DATASET_ID, name=Subset.SENTENCES.value, split="test", revision=revision)
    now = time.time()
    summary: dict[str, float] = {}

    for source_dataset in SourceDataset:
        source_ds = ds.filter(lambda row: row["source_dataset"] == source_dataset.value)
        if max_samples is not None:
            source_ds = source_ds.select(range(min(max_samples, len(source_ds))))

        y_true = [[Entity(**e) for e in row["entities"]] for row in source_ds]
        y_pred = [_detected_spans(row["text"]) for row in source_ds]
        metrics = compute_metrics(y_true=y_true, y_pred=y_pred)
        languages = sorted({row["language"] for row in source_ds})
        score = ScoreResult(
            main_score=metrics.masking.f2,
            f1=metrics.masking.f1,
            f2=metrics.masking.f2,
            precision=metrics.masking.precision,
            recall=metrics.masking.recall,
            ner=metrics.ner,
            hf_subset=Subset.SENTENCES,
            languages=languages,
        )
        task_result = TaskResults(
            dataset_revision=revision,
            task_name=source_dataset.value,
            piimb_version="0.2.0",
            scores={"test": [score]},
            date=now,
        )
        (result_dir / _source_filename(source_dataset.value)).write_text(
            task_result.model_dump_json(indent=2),
            encoding="utf-8",
        )
        summary[source_dataset.value] = metrics.masking.f2

    (result_dir / "model_meta.json").write_text(
        _metadata().model_dump_json(indent=2),
        encoding="utf-8",
    )
    avg_f2 = sum(summary.values()) / len(summary)
    report = {
        "benchmark": "PIIMB",
        "model_id": MODEL_ID,
        "model_dir": MODEL_DIR,
        "dataset": DATASET_ID,
        "dataset_revision": revision,
        "subset": Subset.SENTENCES.value,
        "max_samples_per_dataset": max_samples,
        "average_masking_f2": avg_f2,
        "masking_f2_by_dataset": summary,
        "result_dir": str(result_dir),
        "aana_components": {
            "f_theta": "deterministic PII span proposal detectors",
            "E_phi": "offset validity, PII pattern, and overlap verifiers",
            "R": "local evidence spans from the benchmark text only",
            "Pi_psi": "trim invalid edges and merge overlapping spans",
            "G": "publish only PIIMB-compatible, ground-truth-free predictions and official metrics",
        },
    }
    (result_dir / "aana_piimb_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("eval_outputs/benchmark_scout/piimb_results/results"))
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()
    report = run(output_dir=args.output_dir, max_samples=args.max_samples)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
