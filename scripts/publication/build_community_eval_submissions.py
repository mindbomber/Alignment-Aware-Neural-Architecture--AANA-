#!/usr/bin/env python
"""Build community-eval submission packets from the public AANA evidence pack."""

from __future__ import annotations

import argparse
import json
import pathlib
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK_DIR = ROOT / "eval_outputs" / "hf_peer_review_evidence_pack" / "aana-peer-review-evidence-pack"
OUT_DIR = ROOT / "eval_outputs" / "community_eval_submissions"

MODEL_URL = "https://huggingface.co/mindbomber/aana"
DATASET_URL = "https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack"
SPACE_URL = "https://huggingface.co/spaces/mindbomber/aana-demo"
HUB_URL = "https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4"


SUBMISSIONS = [
    {
        "id": "piimb_privacy",
        "title": "AANA privacy/PII held-out artifact submission",
        "benchmark_repo": "piimb/pii-masking-benchmark-results",
        "repo_type": "dataset",
        "result_file": "data/privacy_heldout_results.json",
        "eval_script": "scripts/evals/run_privacy_pii_adapter_eval.py",
        "manifest_key": "privacy_heldout_results",
        "limitations": [
            "This is an AANA privacy adapter held-out artifact, not a guarantee of perfect PII removal.",
            "One packaged privacy case misses a street-address category while still routing to revise.",
            "Some rows are policy-derived and should be reviewed before treating the result as official.",
            "Production use requires domain-owner policy, secure redaction workflows, and audit-retention review.",
        ],
    },
    {
        "id": "halubench_grounded_qa",
        "title": "AANA grounded-QA/hallucination held-out artifact submission",
        "benchmark_repo": "PatronusAI/HaluBench",
        "repo_type": "dataset",
        "result_file": "data/grounded_qa_heldout_results.json",
        "eval_script": "scripts/evals/run_grounded_qa_adapter_eval.py",
        "manifest_key": "grounded_qa_heldout_results",
        "limitations": [
            "This is a groundedness verifier artifact, not an official HaluBench leaderboard entry.",
            "The RAGTruth-style rows are schema-only fixtures and are not used as public split claims.",
            "Evidence coverage depends on the retrieved evidence supplied to AANA.",
            "Broader human-reviewed hallucination labels are still needed for stronger claims.",
        ],
    },
    {
        "id": "mcp_atlas_tool_use",
        "title": "AANA agent tool-use control artifact submission",
        "benchmark_repo": "ScaleAI/MCP-Atlas",
        "repo_type": "dataset",
        "result_file": "data/tool_use_heldout_results.json",
        "eval_script": "scripts/evals/run_agent_tool_use_control_eval.py",
        "manifest_key": "tool_use_heldout_results",
        "limitations": [
            "This is a pre-tool-call route quality artifact, not proof of end-to-end agent task success.",
            "Labels are policy-derived unless accepted or revised by benchmark maintainers.",
            "AANA should be evaluated as an enforcement/check layer around a capable base agent.",
            "More externally sourced noisy traces and human-reviewed labels are needed.",
        ],
    },
    {
        "id": "mcphunt_tool_use",
        "title": "AANA MCP/tool-use safety artifact submission",
        "benchmark_repo": "lihaonan0716/mcphunt-agent-traces",
        "repo_type": "dataset",
        "result_file": "data/tool_use_heldout_results.json",
        "eval_script": "scripts/evals/run_agent_tool_use_control_eval.py",
        "manifest_key": "tool_use_heldout_results",
        "limitations": [
            "This submission reports AANA route behavior over transformed MCP/tool-use traces.",
            "It is not a claim that AANA solves arbitrary MCP-agent safety or data propagation.",
            "Labels should be challenged by maintainers or independent reviewers.",
            "Unknown tools, private reads, and risky writes should remain fail-closed by default.",
        ],
    },
]


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown(packet: dict[str, Any]) -> str:
    metrics = packet["result"].get("metrics") or packet["manifest_metrics"]
    metric_lines = "\n".join(f"- `{key}`: `{value}`" for key, value in metrics.items())
    limitations = "\n".join(f"- {item}" for item in packet["limitations"])
    return f"""# {packet["title"]}

This is a public community-eval artifact submission for AANA.

## Claim Boundary

AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept.

It is submitted here as a control-layer artifact, not as a raw agent-performance
engine or production certification.

## Result JSON

- Public result artifact: [{DATASET_URL}/blob/main/submissions/{packet["id"]}/result.json]({DATASET_URL}/blob/main/submissions/{packet["id"]}/result.json)
- Full evidence result: [{DATASET_URL}/blob/main/{packet["result_file"]}]({DATASET_URL}/blob/main/{packet["result_file"]})
- Peer-review manifest: [{DATASET_URL}/blob/main/data/aana_peer_review_package_manifest.json]({DATASET_URL}/blob/main/data/aana_peer_review_package_manifest.json)

## Eval Script

- Repo script: `{packet["eval_script"]}`
- Public reproduction command:

```bash
python scripts/publication/build_peer_review_evidence_pack.py
python eval_outputs/hf_peer_review_evidence_pack/aana-peer-review-evidence-pack/scripts/reproduce.py --pack-dir eval_outputs/hf_peer_review_evidence_pack/aana-peer-review-evidence-pack
```

## Metrics

{metric_lines}

## Public Links

- AANA model card: {MODEL_URL}
- AANA evidence dataset: {DATASET_URL}
- Try AANA in 2 minutes: {SPACE_URL}
- AANA artifact hub: {HUB_URL}

## Limitations

{limitations}

## Reviewer Request

Please challenge the result JSON, labels, route choices, false positives,
evidence handling, authorization-state assumptions, and whether this protocol
fits your benchmark's public artifact or submission expectations.
"""


def build(output_dir: pathlib.Path) -> pathlib.Path:
    manifest = _load_json(PACK_DIR / "data" / "aana_peer_review_package_manifest.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []

    for spec in SUBMISSIONS:
        result = _load_json(PACK_DIR / spec["result_file"])
        packet = {
            "id": spec["id"],
            "title": spec["title"],
            "benchmark_repo": spec["benchmark_repo"],
            "repo_type": spec["repo_type"],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "result_file": spec["result_file"],
            "eval_script": spec["eval_script"],
            "manifest_key": spec["manifest_key"],
            "manifest_metrics": manifest["metrics"].get(spec["manifest_key"]),
            "exact_aana_version": manifest["exact_aana_version"],
            "public_links": {
                "model": MODEL_URL,
                "dataset": DATASET_URL,
                "space": SPACE_URL,
                "artifact_hub": HUB_URL,
            },
            "limitations": spec["limitations"],
            "result": result,
        }
        target_dir = output_dir / spec["id"]
        _write_json(target_dir / "result.json", packet)
        (target_dir / "README.md").write_text(_markdown(packet), encoding="utf-8")
        index.append(
            {
                "id": spec["id"],
                "benchmark_repo": spec["benchmark_repo"],
                "repo_type": spec["repo_type"],
                "readme": f"submissions/{spec['id']}/README.md",
                "result_json": f"submissions/{spec['id']}/result.json",
            }
        )

    _write_json(output_dir / "index.json", {"submissions": index})
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=pathlib.Path, default=OUT_DIR)
    args = parser.parse_args()
    print(build(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
