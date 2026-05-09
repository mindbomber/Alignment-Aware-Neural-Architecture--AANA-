#!/usr/bin/env python
"""Build the public AANA peer-review evidence pack dataset artifact."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any


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
- `scripts/reproduce.py`: validates the evidence-pack structure and can run local repo validation commands.
- `reports/aana_peer_review_report.md`: short technical report for reviewers.

## Summary

{_metric_table(results)}

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
