#!/usr/bin/env python
"""Build the public AANA peer-review evidence pack dataset artifact."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agent_integrations import validate_agent_integrations


DEFAULT_OUTPUT_DIR = ROOT / "eval_outputs" / "hf_peer_review_evidence_pack" / "aana-peer-review-evidence-pack"
DATASET_REPO = "mindbomber/aana-peer-review-evidence-pack"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_REPO}"
GITHUB_URL = "https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-"
MODEL_URL = "https://huggingface.co/mindbomber/aana"
SPACE_URL = "https://huggingface.co/spaces/mindbomber/aana-demo"
ARTIFACT_HUB_URL = "https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4"


SOURCE_FILES = {
    "privacy": ROOT / "eval_outputs" / "privacy_pii_adapter_upgrade_results.json",
    "grounded_qa": ROOT / "eval_outputs" / "grounded_qa_adapter_upgrade_results.json",
    "tool_use": ROOT / "eval_outputs" / "agent_tool_use_control_upgrade_results.json",
}

DROP_KEYS = {
    "stdout",
    "stderr",
    "stdout_log",
    "stderr_log",
    "audit_log_path",
}
LOCAL_PATH_RE = re.compile(r"[A-Za-z]:\\[^\n\r\t\"]+")


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required evidence artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _project_metadata() -> dict[str, Any]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    dirty = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "package_name": project.get("name"),
        "aana_version": project.get("version"),
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else "unknown",
        "git_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "python_requires": project.get("requires-python"),
    }


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items() if key not in DROP_KEYS}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT), "<repo>")
        value = LOCAL_PATH_RE.sub("<local_path>", value)
    return value


def _with_metadata(name: str, source_path: pathlib.Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact": name,
        "source_file": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "claim_boundary": (
            "Measured held-out or validation artifact for AANA as an audit/control/"
            "verification/correction layer. This is not evidence that AANA is a raw "
            "agent-performance engine."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "links": {
            "dataset": DATASET_URL,
            "artifact_hub": ARTIFACT_HUB_URL,
            "model_card": MODEL_URL,
            "space": SPACE_URL,
            "github": GITHUB_URL,
        },
        **payload,
    }


def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("request_id") or row.get("name") or "unknown")


def _collect_failure_cases(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        reasons: list[str] = []
        if row.get("expected_route") != row.get("actual_route") and row.get("actual_route") is not None:
            reasons.append("route_mismatch")
        if row.get("expected_label") != row.get("actual_label") and row.get("actual_label") is not None:
            reasons.append("label_mismatch")
        expected_categories = sorted(row.get("expected_categories") or [])
        detected_categories = sorted(row.get("detected_categories") or [])
        if expected_categories != detected_categories:
            reasons.append("category_mismatch")
        if row.get("route_correct") is False or row.get("correct") is False:
            reasons.append("scoring_mismatch")
        if reasons:
            failures.append(
                {
                    "id": _row_id(row),
                    "source_dataset": row.get("source_dataset"),
                    "reasons": reasons,
                    "expected_route": row.get("expected_route"),
                    "actual_route": row.get("actual_route"),
                    "expected_label": row.get("expected_label"),
                    "actual_label": row.get("actual_label"),
                    "expected_categories": expected_categories,
                    "detected_categories": detected_categories,
                }
            )
    return failures


def _collect_false_positives(payload: dict[str, Any]) -> list[dict[str, Any]]:
    false_positives: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        expected_route = row.get("expected_route")
        actual_route = row.get("actual_route") or row.get("recommended_action")
        expected_block = row.get("expected_block")
        blocked = row.get("blocked")
        if expected_route == "accept" and actual_route and actual_route != "accept":
            false_positives.append(
                {
                    "id": _row_id(row),
                    "source_dataset": row.get("source_dataset"),
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                }
            )
        elif expected_block is False and blocked is True:
            false_positives.append(
                {
                    "id": _row_id(row),
                    "source_dataset": row.get("source_dataset"),
                    "expected_block": expected_block,
                    "blocked": blocked,
                }
            )
    return false_positives


def _split_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for source in payload.get("dataset_sources", []):
        summary.append(
            {
                "dataset_name": source.get("dataset_name"),
                "allowed_use": source.get("registry_allowed_use"),
                "split_boundary": source.get("split_boundary")
                or "Use registered calibration splits for tuning and held-out/external-reporting splits for public claims.",
                "schema_role": source.get("schema_role"),
            }
        )
    return summary


def _latency_summary(integration: dict[str, Any]) -> dict[str, Any]:
    checks = integration.get("checks", [])
    latencies = [
        check.get("latency_ms")
        for check in checks
        if isinstance(check.get("latency_ms"), int | float)
    ]
    return {
        "integration_check_latency_ms": {
            "count": len(latencies),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "avg": round(sum(latencies) / len(latencies), 3) if latencies else None,
        },
        "per_check": [
            {
                "name": check.get("name"),
                "valid": check.get("valid"),
                "latency_ms": check.get("latency_ms"),
            }
            for check in checks
        ],
        "adapter_eval_latency": "not_measured_in_this_pack",
    }


def _package_manifest(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_failures: list[dict[str, Any]] = []
    all_false_positives: list[dict[str, Any]] = []
    split_boundaries: dict[str, Any] = {}
    for name, payload in results.items():
        failures = _collect_failure_cases(payload)
        false_positives = _collect_false_positives(payload)
        all_failures.extend({"artifact": name, **item} for item in failures)
        all_false_positives.extend({"artifact": name, **item} for item in false_positives)
        split_boundaries[name] = _split_summary(payload)

    return {
        "artifact": "aana_peer_review_package_manifest",
        "exact_aana_version": _project_metadata(),
        "bundle_surfaces": {
            "model_repo": MODEL_URL,
            "dataset_repo": DATASET_URL,
            "space": SPACE_URL,
            "paper_or_report_page": f"{GITHUB_URL}/blob/master/docs/aana-agent-action-technical-report.md",
            "artifact_hub": ARTIFACT_HUB_URL,
        },
        "eval_cases": {
            name: {
                "case_count": payload.get("metrics", {}).get("case_count", payload.get("total")),
                "source_file": payload.get("source_file"),
            }
            for name, payload in results.items()
        },
        "calibration_vs_heldout_split": split_boundaries,
        "metrics": {
            name: payload.get("metrics") or {
                "valid": payload.get("valid"),
                "passed": payload.get("passed"),
                "total": payload.get("total"),
            }
            for name, payload in results.items()
        },
        "failure_cases": all_failures,
        "false_positives": all_false_positives,
        "unsupported_domains": [
            "Domains without a registered and held-out validated adapter family.",
            "Production medical diagnosis, legal advice, financial advice, or regulated approval workflows without domain-owner policy and human escalation.",
            "Real sends, deletes, purchases, exports, fund transfers, production deploys, or account changes in public demos.",
            "Raw agent task-success claims where AANA is used as the planner rather than as a check/control layer.",
            "Benchmark leaderboard claims unless the benchmark maintainer accepts the protocol and submission channel.",
        ],
        "latency": _latency_summary(results["agent_integration_validation"]),
        "commands_to_reproduce": [
            "python scripts/build_peer_review_evidence_pack.py",
            "python eval_outputs/hf_peer_review_evidence_pack/aana-peer-review-evidence-pack/scripts/reproduce.py --pack-dir eval_outputs/hf_peer_review_evidence_pack/aana-peer-review-evidence-pack",
            "python scripts/validate_agent_integrations.py",
        ],
        "claim_boundary": (
            "This package supports review of AANA as an audit/control/verification/"
            "correction layer. It does not prove AANA as a raw agent-performance engine."
        ),
    }


def _metric_table(results: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| Artifact | Cases | Key metrics |",
        "|---|---:|---|",
    ]
    for name, payload in results.items():
        metrics = payload.get("metrics", {})
        case_count = metrics.get("case_count", payload.get("total", "n/a"))
        metric_text = ", ".join(
            f"{key}={value}" for key, value in metrics.items() if key != "case_count"
        )
        if not metric_text and "valid" in payload:
            metric_text = f"valid={payload.get('valid')}, passed={payload.get('passed')}/{payload.get('total')}"
        lines.append(f"| {name} | {case_count} | {metric_text} |")
    return "\n".join(lines)


def _readme(results: dict[str, dict[str, Any]]) -> str:
    return f"""---
license: mit
pretty_name: AANA Peer Review Evidence Pack
tags:
  - ai-safety
  - agent-control
  - agent-safety
  - auditability
  - grounded-qa
  - hallucination
  - pii
  - tool-use
  - verification
---

# AANA Peer Review Evidence Pack

This dataset packages the current public evidence for AANA as an architecture for
making agents more auditable, safer, more grounded, and more controllable.

The claim boundary is intentionally narrow:

- AANA is production-candidate as an audit/control/verification/correction layer.
- AANA is not yet proven as a raw agent-performance engine.
- Results here are measured held-out or validation artifacts, not official
  leaderboard proof unless a benchmark maintainer explicitly accepts them.
- Probe-enabled or answer-key-style diagnostic runs are excluded from this pack.

## Contents

- `data/privacy_heldout_results.json`: privacy/PII adapter held-out validation.
- `data/grounded_qa_heldout_results.json`: grounded QA and hallucination adapter validation.
- `data/tool_use_heldout_results.json`: agent tool-use control validation.
- `data/agent_integration_validation.json`: OpenAI-style wrapper, FastAPI policy service, MCP tool, and controlled-agent eval smoke validation.
- `data/aana_peer_review_package_manifest.json`: exact AANA version, split boundaries, metrics, failures, false positives, unsupported domains, latency, and reproduction commands.
- `scripts/reproduce.py`: validates the evidence-pack structure and can run local repo validation commands.
- `reports/aana_peer_review_report.md`: short technical report for reviewers.

## Summary

{_metric_table(results)}

## Peer-Review Package Checklist

- Exact AANA version: recorded in `data/aana_peer_review_package_manifest.json`.
- Eval cases: included in each `data/*_results.json` artifact.
- Calibration split vs held-out split: recorded per source dataset in the manifest.
- Metrics: summarized below and stored in each result artifact.
- Failure cases and false positives: extracted into the manifest.
- Unsupported domains: listed in the manifest and report.
- Latency: integration latency is measured in the manifest; adapter-eval latency is marked as not yet measured.
- Command to reproduce: `python scripts/reproduce.py --pack-dir .`

## Public Links

- AANA model card: [{MODEL_URL}]({MODEL_URL})
- AANA demo Space: [{SPACE_URL}]({SPACE_URL})
- GitHub repository: [{GITHUB_URL}]({GITHUB_URL})
- Peer-review evidence pack: [{DATASET_URL}]({DATASET_URL})
- Public artifact hub: [{ARTIFACT_HUB_URL}]({ARTIFACT_HUB_URL})

## Reproduction

To validate the downloaded evidence-pack files:

```bash
python scripts/reproduce.py --pack-dir .
```

To rerun local integration checks from a cloned AANA repository:

```bash
python scripts/reproduce.py --pack-dir . --repo-root /path/to/Alignment-Aware-Neural-Architecture--AANA-
```

The local rerun checks the current repository implementation; numbers may change
when adapters, thresholds, or integration wrappers change.
"""


def _report(results: dict[str, dict[str, Any]]) -> str:
    return f"""# AANA Peer Review Evidence Report

## Claim Under Review

AANA is an architecture for making agents more auditable, safer, more grounded,
and more controllable. It is currently positioned as an audit, control,
verification, and correction layer around agents:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

AANA is not presented here as a standalone base model or as a proven raw
agent-performance engine.

## Evidence Pack

This report summarizes the machine-readable artifacts in
[{DATASET_REPO}]({DATASET_URL}).

The canonical public artifact hub is
[{ARTIFACT_HUB_URL}]({ARTIFACT_HUB_URL}).

{_metric_table(results)}

## What The Artifacts Test

- Privacy/PII: PII recall, false-positive rate, safe allow rate, redaction
  correctness, and route accuracy across PIIMB/OpenPII/Nemotron-style cases.
- Grounded QA/hallucination: unsupported-claim recall, answerable safe allow
  rate, citation/evidence coverage, over-refusal rate, and route accuracy.
- Agent tool-use: unsafe-action recall, private-read/write gating,
  ask/defer/refuse quality, schema failure rate, and safe allow rate.
- Agent integrations: wrapped tools, FastAPI policy service, MCP tool surface,
  and controlled-agent eval harness all fail closed when AANA blocks execution.

## Limitations

- Some labels are policy-derived from AANA evaluation scripts rather than
  benchmark-maintainer or independent human-review labels.
- The pack validates routing, evidence handling, redaction, and execution
  blocking. It does not prove arbitrary end-to-end task success.
- The adapter families still need broader held-out coverage and latency testing
  before stronger production claims.
- Official leaderboard or benchmark claims should use benchmark-native
  submission channels and maintainer-accepted protocols.

## Reviewer Questions

1. Are the route labels and metrics sufficient for an auxiliary safety/control
   track in agent benchmarks?
2. Which fields should become mandatory in an agent pre-tool-call standard?
3. Should future reporting prioritize unsafe-action recall, safe allow rate,
   route accuracy, or task-success impact under AANA enforcement?
4. Which external datasets should become the next held-out validation sources?
"""


def _reproduce_script() -> str:
    return '''#!/usr/bin/env python
"""Validate the AANA peer-review evidence pack and optionally rerun local checks."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys


REQUIRED_FILES = [
    "README.md",
    "data/aana_peer_review_package_manifest.json",
    "data/privacy_heldout_results.json",
    "data/grounded_qa_heldout_results.json",
    "data/tool_use_heldout_results.json",
    "data/agent_integration_validation.json",
    "reports/aana_peer_review_report.md",
]


def _load_json(path: pathlib.Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_pack(pack_dir: pathlib.Path) -> dict:
    missing = [name for name in REQUIRED_FILES if not (pack_dir / name).exists()]
    summaries = {}
    if not missing:
        for name in REQUIRED_FILES:
            if name.endswith(".json"):
                payload = _load_json(pack_dir / name)
                summaries[name] = {
                    "artifact": payload.get("artifact"),
                    "metrics": payload.get("metrics"),
                    "valid": payload.get("valid"),
                    "passed": payload.get("passed"),
                    "total": payload.get("total"),
                }
    return {
        "valid": not missing,
        "missing": missing,
        "summaries": summaries,
    }


def run_repo_checks(repo_root: pathlib.Path) -> dict:
    commands = [
        [sys.executable, "scripts/validate_agent_integrations.py", "--json"],
    ]
    results = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=180,
        )
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
    return {"valid": all(item["returncode"] == 0 for item in results), "commands": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--repo-root", type=pathlib.Path, help="Optional local AANA repo checkout for live integration validation.")
    args = parser.parse_args()

    report = {"pack": validate_pack(args.pack_dir)}
    if args.repo_root:
        report["repo_checks"] = run_repo_checks(args.repo_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pack"]["valid"] and report.get("repo_checks", {"valid": True})["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_pack(output_dir: pathlib.Path) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)

    privacy = _with_metadata("privacy_heldout_results", SOURCE_FILES["privacy"], _sanitize(_load_json(SOURCE_FILES["privacy"])))
    grounded = _with_metadata("grounded_qa_heldout_results", SOURCE_FILES["grounded_qa"], _sanitize(_load_json(SOURCE_FILES["grounded_qa"])))
    tool_use = _with_metadata("tool_use_heldout_results", SOURCE_FILES["tool_use"], _sanitize(_load_json(SOURCE_FILES["tool_use"])))
    integration = _with_metadata(
        "agent_integration_validation",
        ROOT / "scripts" / "validate_agent_integrations.py",
        _sanitize(validate_agent_integrations()),
    )

    results = {
        "privacy_heldout_results": privacy,
        "grounded_qa_heldout_results": grounded,
        "tool_use_heldout_results": tool_use,
        "agent_integration_validation": integration,
    }

    _write_json(output_dir / "data" / "privacy_heldout_results.json", privacy)
    _write_json(output_dir / "data" / "grounded_qa_heldout_results.json", grounded)
    _write_json(output_dir / "data" / "tool_use_heldout_results.json", tool_use)
    _write_json(output_dir / "data" / "agent_integration_validation.json", integration)
    _write_json(output_dir / "data" / "aana_peer_review_package_manifest.json", _package_manifest(results))
    (output_dir / "README.md").write_text(_readme(results), encoding="utf-8")
    (output_dir / "reports" / "aana_peer_review_report.md").write_text(_report(results), encoding="utf-8")
    reproduce = output_dir / "scripts" / "reproduce.py"
    reproduce.write_text(_reproduce_script(), encoding="utf-8")
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    output_dir = build_pack(args.output_dir)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
