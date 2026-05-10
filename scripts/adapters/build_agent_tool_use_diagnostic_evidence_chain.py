#!/usr/bin/env python
"""Build the AANA agent tool-use diagnostic evidence chain summary."""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_TOOL_USE = ROOT / "eval_outputs" / "agent_tool_use_hf_experiment_results.json"
DEFAULT_READ_ROUTING = ROOT / "eval_outputs" / "public_private_read_routing_hf_experiment_results.json"
DEFAULT_AUTH_ROBUSTNESS = ROOT / "eval_outputs" / "authorization_robustness_hf_experiment_results.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "aana_agent_tool_use_diagnostic_evidence_chain.json"


def _load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _method_metrics(payload: dict[str, Any], method: str = "deterministic_aana_v2") -> dict[str, Any]:
    return dict(((payload.get("heldout_validation") or {}).get("metrics_by_method") or {}).get(method) or {})


def _metric(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    return float(value) if isinstance(value, int | float) else 0.0


def build_chain(*, tool_use: pathlib.Path, read_routing: pathlib.Path, auth_robustness: pathlib.Path) -> dict[str, Any]:
    tool_use_payload = _load(tool_use)
    read_payload = _load(read_routing)
    auth_payload = _load(auth_robustness)

    tool_v2 = _method_metrics(tool_use_payload)
    read_v2 = _method_metrics(read_payload)
    auth_v2 = _method_metrics(auth_payload)
    plain_tool = _method_metrics(tool_use_payload, "plain_permissive_agent")
    plain_read = _method_metrics(read_payload, "plain_permissive_agent")
    plain_auth = _method_metrics(auth_payload, "plain_permissive_agent")

    metrics = {
        "tool_use_v2_unsafe_action_recall": _metric(tool_v2, "unsafe_action_recall"),
        "tool_use_v2_safe_allow_rate": _metric(tool_v2, "safe_allow_rate"),
        "tool_use_v2_schema_failure_rate": _metric(tool_v2, "schema_failure_rate"),
        "tool_use_plain_unsafe_action_recall": _metric(plain_tool, "unsafe_action_recall"),
        "read_routing_v2_public_read_allow_rate": _metric(read_v2, "public_read_allow_rate"),
        "read_routing_v2_private_read_escalation_rate": _metric(read_v2, "private_read_escalation_rate"),
        "read_routing_v2_authorized_private_read_allow_rate": _metric(read_v2, "authorized_private_read_allow_rate"),
        "read_routing_v2_false_public_allow_rate": _metric(read_v2, "false_public_allow_rate"),
        "read_routing_v2_schema_failure_rate": _metric(read_v2, "schema_failure_rate"),
        "read_routing_plain_false_public_allow_rate": _metric(plain_read, "false_public_allow_rate"),
        "authorization_v2_missing_auth_recall": _metric(auth_v2, "missing_auth_recall"),
        "authorization_v2_stale_evidence_defer_rate": _metric(auth_v2, "stale_evidence_defer_rate"),
        "authorization_v2_contradictory_evidence_defer_refuse_rate": _metric(auth_v2, "contradictory_evidence_defer_refuse_rate"),
        "authorization_v2_private_read_mislabel_correction_rate": _metric(auth_v2, "private_read_mislabel_correction_rate"),
        "authorization_v2_safe_public_read_allow_rate": _metric(auth_v2, "safe_public_read_allow_rate"),
        "authorization_v2_over_block_rate": _metric(auth_v2, "over_block_rate"),
        "authorization_v2_route_family_accuracy": _metric(auth_v2, "route_family_accuracy"),
        "authorization_plain_missing_auth_recall": _metric(plain_auth, "missing_auth_recall"),
        "authorization_plain_stale_evidence_defer_rate": _metric(plain_auth, "stale_evidence_defer_rate"),
        "authorization_plain_private_read_mislabel_correction_rate": _metric(plain_auth, "private_read_mislabel_correction_rate"),
    }

    return {
        "schema_version": "0.1",
        "result_label": "diagnostic_heldout_chain",
        "claim_boundary": (
            "AANA is evaluated as an audit/control/verification/correction layer for agent tool calls. "
            "This artifact does not claim raw autonomous task-performance superiority."
        ),
        "public_language": "Report measured rates, baseline comparisons, and limitations; do not present as official leaderboard or human-reviewed benchmark proof.",
        "evidence_chain": [
            {
                "id": "broad_tool_use_control",
                "artifact": str(tool_use.relative_to(ROOT)),
                "experiment_id": tool_use_payload.get("experiment_id"),
                "summary": "Broad tool-call control comparison against a plain permissive agent.",
            },
            {
                "id": "public_private_read_routing",
                "artifact": str(read_routing.relative_to(ROOT)),
                "experiment_id": read_payload.get("experiment_id"),
                "summary": "Focused public-read versus private-read routing validation.",
            },
            {
                "id": "authorization_robustness",
                "artifact": str(auth_robustness.relative_to(ROOT)),
                "experiment_id": auth_payload.get("experiment_id"),
                "summary": "Noisy authorization/evidence perturbation validation.",
            },
        ],
        "metrics": metrics,
        "limitations": [
            "Labels remain diagnostic and contract/span-derived unless separately reviewed by humans or benchmark maintainers.",
            "HF rows are transformed into Agent Action Contract v1 events, so this validates AANA's control layer rather than raw agent task success.",
            "No raw prompts, document text, full arguments, tool outputs, or private spans are copied into this summary artifact.",
            "Official external claims still require maintainer-accepted protocols or human-reviewed labels.",
        ],
        "raw_payload_logged": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-use", default=str(DEFAULT_TOOL_USE))
    parser.add_argument("--read-routing", default=str(DEFAULT_READ_ROUTING))
    parser.add_argument("--auth-robustness", default=str(DEFAULT_AUTH_ROBUSTNESS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    output = pathlib.Path(args.output)
    payload = build_chain(
        tool_use=pathlib.Path(args.tool_use),
        read_routing=pathlib.Path(args.read_routing),
        auth_robustness=pathlib.Path(args.auth_robustness),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        metrics = payload["metrics"]
        print(
            "pass -- "
            f"tool_use_unsafe_recall={metrics['tool_use_v2_unsafe_action_recall']:.3f} "
            f"read_private_escalation={metrics['read_routing_v2_private_read_escalation_rate']:.3f} "
            f"auth_missing_auth_recall={metrics['authorization_v2_missing_auth_recall']:.3f} "
            f"auth_over_block_rate={metrics['authorization_v2_over_block_rate']:.3f} "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
