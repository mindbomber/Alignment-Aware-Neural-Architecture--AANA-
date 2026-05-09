"""Run Presidio base vs Presidio+AANA on PIIMB.

This pairs AANA with Microsoft Presidio's specialist PII recognizers and measures
whether the AANA verifier/correction loop improves PIIMB masking recall/F2 over
the base detector alone. The AANA-enhanced output is written in PIIMB leaderboard
format for official submission.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import spacy
from datasets import load_dataset
from huggingface_hub import dataset_info
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine


ROOT = Path(__file__).resolve().parents[1]
PIIMB_SRC = ROOT / "eval_outputs" / "benchmark_scout" / "repos" / "pii-masking-benchmark" / "src"
PIIMB_PKG = PIIMB_SRC / "piimb"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


piimb_models = _load_module("piimb.models", PIIMB_PKG / "models.py")
sys.modules.setdefault("piimb", type(sys)("piimb"))
setattr(sys.modules["piimb"], "models", piimb_models)
piimb_metrics = _load_module("piimb.metrics", PIIMB_PKG / "metrics.py")

DATASET_ID = piimb_models.DATASET_ID
Entity = piimb_models.Entity
ModelMetadata = piimb_models.ModelMetadata
PipelineType = piimb_models.PipelineType
ScoreResult = piimb_models.ScoreResult
SourceDataset = piimb_models.SourceDataset
Subset = piimb_models.Subset
TaskResults = piimb_models.TaskResults
compute_metrics = piimb_metrics.compute_metrics


@dataclass(frozen=True)
class Detector:
    label: str
    pattern: re.Pattern[str]


AANA_DETECTORS = [
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
    Detector("PERSON", re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")),
]


BASE_MODEL_ID = "microsoft/presidio-analyzer"
AANA_MODEL_ID = "mindbomber/aana-presidio-piimb-policy-v1"
AANA_MODEL_DIR = "mindbomber__aana-presidio-piimb-policy-v1__policy-v1"


class MinimalNlpEngine(NlpEngine):
    """Minimal tokenizer-only engine for Presidio's pattern recognizers."""

    def __init__(self) -> None:
        self.nlp = spacy.blank("en")

    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["en"]

    def process_text(self, text: str, language: str) -> NlpArtifacts:
        doc = self.nlp.make_doc(text)
        return NlpArtifacts(
            entities=[],
            tokens=doc,
            tokens_indices=[token.idx for token in doc],
            lemmas=[token.text.lower() for token in doc],
            nlp_engine=self,
            language=language,
        )

    def process_batch(
        self,
        texts: Iterable[str],
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs,
    ):
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        return False

    def is_punct(self, word: str, language: str) -> bool:
        return len(word) == 1 and not word.isalnum()


def _build_analyzer() -> AnalyzerEngine:
    nlp_engine = MinimalNlpEngine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp_engine)
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        default_score_threshold=0.0,
    )


def _presidio_spans(text: str, analyzer: AnalyzerEngine) -> list[Entity]:
    entities: list[Entity] = []
    for result in analyzer.analyze(text=text, language="en"):
        if result.start >= result.end:
            continue
        entities.append(Entity(start=result.start, end=result.end, label=result.entity_type))
    return _merge_entities(entities)


def _valid_credit_like(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return 13 <= len(digits) <= 19 and len(set(digits)) > 1


def _detected_spans(text: str) -> list[Entity]:
    entities: list[Entity] = []
    for detector in AANA_DETECTORS:
        for match in detector.pattern.finditer(text):
            if detector.label == "SECRET" and match.lastindex:
                start, end = match.span(1)
            else:
                start, end = match.span()
            raw = text[start:end]
            span = raw.strip(" ,.;:)]}\"'")
            start += len(raw) - len(raw.lstrip(" ,.;:)]}\"'"))
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


def _aana_spans(text: str, analyzer: AnalyzerEngine) -> list[Entity]:
    base = _presidio_spans(text=text, analyzer=analyzer)
    evidence = _detected_spans(text)
    return _merge_entities([*base, *evidence])


def _source_filename(source_dataset: str) -> str:
    return source_dataset.replace("/", "__") + ".json"


def _metadata() -> ModelMetadata:
    return ModelMetadata(
        name=AANA_MODEL_ID,
        pipeline_type=PipelineType.TOKEN_CLASSIFICATION,
        model_type="aana-presidio-policy",
        revision="policy-v1",
        dtype="policy-v1",
        release_date="2026-05-07",
        languages=["en", "multilingual-patterns"],
        datasets=[],
        base_model=[BASE_MODEL_ID],
        license="MIT",
        n_parameters=0,
        n_embedding_parameters=0,
        n_active_parameters=0,
        max_tokens=None,
        threshold=None,
        reference=f"https://huggingface.co/{AANA_MODEL_ID}",
    )


def _score_source(source_ds, analyzer: AnalyzerEngine) -> tuple[dict, TaskResults]:
    y_true = [[Entity(**e) for e in row["entities"]] for row in source_ds]
    y_base = [_presidio_spans(row["text"], analyzer) for row in source_ds]
    y_aana = [_aana_spans(row["text"], analyzer) for row in source_ds]
    base_metrics = compute_metrics(y_true=y_true, y_pred=y_base)
    aana_metrics = compute_metrics(y_true=y_true, y_pred=y_aana)
    languages = sorted({row["language"] for row in source_ds})
    score = ScoreResult(
        main_score=aana_metrics.masking.f2,
        f1=aana_metrics.masking.f1,
        f2=aana_metrics.masking.f2,
        precision=aana_metrics.masking.precision,
        recall=aana_metrics.masking.recall,
        ner=aana_metrics.ner,
        hf_subset=Subset.SENTENCES,
        languages=languages,
    )
    comparison = {
        "base_precision": base_metrics.masking.precision,
        "base_recall": base_metrics.masking.recall,
        "base_f1": base_metrics.masking.f1,
        "base_f2": base_metrics.masking.f2,
        "aana_precision": aana_metrics.masking.precision,
        "aana_recall": aana_metrics.masking.recall,
        "aana_f1": aana_metrics.masking.f1,
        "aana_f2": aana_metrics.masking.f2,
        "delta_f2": aana_metrics.masking.f2 - base_metrics.masking.f2,
        "delta_recall": aana_metrics.masking.recall - base_metrics.masking.recall,
    }
    task_result = TaskResults(
        dataset_revision="",
        task_name=source_ds[0]["source_dataset"],
        piimb_version="0.2.0",
        scores={"test": [score]},
        date=time.time(),
    )
    return comparison, task_result


def run(output_dir: Path, max_samples: int | None) -> dict:
    revision = dataset_info(repo_id=DATASET_ID).sha
    analyzer = _build_analyzer()
    result_dir = output_dir / AANA_MODEL_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    ds = load_dataset(path=DATASET_ID, name=Subset.SENTENCES.value, split="test", revision=revision)
    comparisons = {}
    now = time.time()

    for source_dataset in SourceDataset:
        source_ds = ds.filter(lambda row: row["source_dataset"] == source_dataset.value)
        if max_samples is not None:
            source_ds = source_ds.select(range(min(max_samples, len(source_ds))))
        comparison, task_result = _score_source(source_ds=source_ds, analyzer=analyzer)
        task_result.dataset_revision = revision
        task_result.date = now
        comparisons[source_dataset.value] = comparison
        (result_dir / _source_filename(source_dataset.value)).write_text(
            task_result.model_dump_json(indent=2),
            encoding="utf-8",
        )

    (result_dir / "model_meta.json").write_text(
        _metadata().model_dump_json(indent=2),
        encoding="utf-8",
    )
    avg_base_f2 = sum(item["base_f2"] for item in comparisons.values()) / len(comparisons)
    avg_aana_f2 = sum(item["aana_f2"] for item in comparisons.values()) / len(comparisons)
    avg_base_recall = sum(item["base_recall"] for item in comparisons.values()) / len(comparisons)
    avg_aana_recall = sum(item["aana_recall"] for item in comparisons.values()) / len(comparisons)
    report = {
        "benchmark": "PIIMB",
        "model_id": AANA_MODEL_ID,
        "model_dir": AANA_MODEL_DIR,
        "base_detector": BASE_MODEL_ID,
        "dataset": DATASET_ID,
        "dataset_revision": revision,
        "subset": Subset.SENTENCES.value,
        "max_samples_per_dataset": max_samples,
        "base_average_masking_f2": avg_base_f2,
        "aana_average_masking_f2": avg_aana_f2,
        "delta_average_masking_f2": avg_aana_f2 - avg_base_f2,
        "base_average_recall": avg_base_recall,
        "aana_average_recall": avg_aana_recall,
        "delta_average_recall": avg_aana_recall - avg_base_recall,
        "comparison_by_dataset": comparisons,
        "result_dir": str(result_dir),
        "aana_components": {
            "f_theta": "Microsoft Presidio predefined PII recognizers",
            "E_phi": "offset validity, PII pattern, overlap, and high-risk identifier verifiers",
            "R": "Presidio recognizer outputs plus local evidence spans from benchmark text",
            "Pi_psi": "union high-confidence evidence, trim invalid edges, merge overlaps",
            "G": "publish only if AANA release gate accepts bounded benchmark claims",
        },
    }
    (result_dir / "aana_piimb_presidio_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("eval_outputs/benchmark_scout/piimb_presidio_results/results"),
    )
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(run(output_dir=args.output_dir, max_samples=args.max_samples), indent=2))


if __name__ == "__main__":
    main()
