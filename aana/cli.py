"""Runtime-focused command line interface for the public AANA package."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from aana.sdk import architecture_decision, with_architecture_decision
from eval_pipeline import agent_api
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2, validate_event as validate_tool_precheck_event
from eval_pipeline.production_candidate_evidence_pack import (
    load_manifest as load_evidence_pack_manifest,
    validate_production_candidate_evidence_pack,
)
from eval_pipeline.semantic_verifier import build_semantic_verifier


ROOT = pathlib.Path.cwd()
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_EVIDENCE_PACK = ROOT / "examples" / "production_candidate_evidence_pack.json"
PUBLIC_ARCHITECTURE_CLAIM = "AANA makes agents more auditable, safer, more grounded, and more controllable."


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_json(path: str | pathlib.Path) -> dict:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def command_agent_check(args: argparse.Namespace) -> int:
    started_at = time.perf_counter()
    event = _load_json(args.event)
    if args.evidence_registry or args.require_structured_evidence:
        registry = agent_api.load_evidence_registry(args.evidence_registry) if args.evidence_registry else None
        report = agent_api.validate_event(
            event,
            evidence_registry=registry,
            require_structured_evidence=args.require_structured_evidence,
        )
        if not report["valid"]:
            _print_json({"event_validation": report})
            return 1
    response = agent_api.check_event(
        event,
        gallery_path=args.gallery,
        adapter_id=args.adapter_id,
        semantic_verifier_kind=args.semantic_verifier,
        semantic_model=args.semantic_model,
    )
    response.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    if args.shadow_mode:
        response = agent_api.apply_shadow_mode(response)
    record = agent_api.audit_event_check(event, response)
    if args.audit_log:
        agent_api.append_audit_record(args.audit_log, record)
    response = with_architecture_decision(response, event, audit_record=record)
    _print_json(response)
    return 0 if args.shadow_mode or response.get("gate_decision") == "pass" else 1


def command_pre_tool_check(args: argparse.Namespace) -> int:
    started_at = time.perf_counter()
    event = _load_json(args.event)
    validation_errors = validate_tool_precheck_event(event)
    if args.validate_only:
        response = {
            "valid": not validation_errors,
            "errors": validation_errors,
            "schema_version": "aana.agent_tool_precheck.v1",
        }
        _print_json(response)
        return 0 if response["valid"] else 1
    if validation_errors and args.strict_validation:
        result = {
            "gate_decision": "fail",
            "recommended_action": "refuse",
            "hard_blockers": ["schema_validation_failed"],
            "aix": {"score": 0.0, "decision": "refuse", "hard_blockers": ["schema_validation_failed"]},
            "audit_metadata": {"latency_ms": round((time.perf_counter() - started_at) * 1000, 3)},
        }
        record = agent_api.audit_tool_precheck(
            event,
            result,
            latency_ms=result["audit_metadata"]["latency_ms"],
            surface="cli",
            route="pre-tool-check",
        )
        if args.audit_log:
            agent_api.append_audit_record(args.audit_log, record)
        _print_json(
            {
                "valid": False,
                "errors": validation_errors,
                "schema_version": "aana.agent_tool_precheck.v1",
                "architecture_decision": architecture_decision(result, event, audit_record=record),
            }
        )
        return 1
    semantic_verifier = build_semantic_verifier(args.semantic_verifier, model=args.semantic_model)
    result = (
        gate_pre_tool_call_v2(event, semantic_verifier=semantic_verifier)
        if args.gate_version == "v2"
        else gate_pre_tool_call(event)
    )
    result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    record = agent_api.audit_tool_precheck(
        event,
        result,
        latency_ms=result["audit_metadata"]["latency_ms"],
        surface="cli",
        route="pre-tool-check",
    )
    if args.audit_log:
        agent_api.append_audit_record(args.audit_log, record)
    response = with_architecture_decision(result, event, audit_record=record)
    _print_json(response)
    return 0 if response.get("gate_decision") == "pass" else 1


def command_audit_summary(args: argparse.Namespace) -> int:
    summary = agent_api.summarize_audit_file(args.audit_log)
    if args.json:
        _print_json(summary)
        return 0
    print(f"AANA audit summary: {summary['total']} record(s).")
    print("Gate decisions:")
    for key, value in sorted(summary["gate_decisions"].items()):
        print(f"- {key}: {value}")
    print("Recommended actions:")
    for key, value in sorted(summary["recommended_actions"].items()):
        print(f"- {key}: {value}")
    return 0


def command_evidence_pack(args: argparse.Namespace) -> int:
    manifest = load_evidence_pack_manifest(args.manifest)
    report = validate_production_candidate_evidence_pack(
        manifest,
        root=ROOT,
        require_existing_artifacts=args.require_existing_artifacts,
    )
    response = {
        "architecture_claim": PUBLIC_ARCHITECTURE_CLAIM,
        "claim_boundary": manifest.get("claim_boundary", {}),
        "evidence_status": manifest.get("evidence_status"),
        "report_path": manifest.get("report_path"),
        "required_artifacts": manifest.get("required_artifacts", []),
        "limitations": manifest.get("limitations", {}),
        "validation": report,
    }
    _print_json(response)
    return 0 if report.get("valid") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "AANA runtime CLI. Research, benchmark, and HF experiment tooling stays "
            "repo-local under scripts/ and is not installed as public package commands."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    agent = subparsers.add_parser("agent-check", help="Check an AI-agent event against a gallery adapter.")
    agent.add_argument("--event", required=True, help="Agent event JSON.")
    agent.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    agent.add_argument("--adapter-id", default=None, help="Override adapter_id when the event does not include one.")
    agent.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON.")
    agent.add_argument("--require-structured-evidence", action="store_true")
    agent.add_argument("--semantic-verifier", choices=["none", "openai"], default="none")
    agent.add_argument("--semantic-model", default=None)
    agent.add_argument("--shadow-mode", action="store_true")
    agent.add_argument("--audit-log", default=None)
    agent.set_defaults(func=command_agent_check)

    pre_tool = subparsers.add_parser("pre-tool-check", help="Check an Agent Action Contract v1 tool call before execution.")
    pre_tool.add_argument("--event", required=True, help="Agent Action Contract v1 JSON.")
    pre_tool.add_argument("--gate-version", choices=["v1", "v2"], default="v2")
    pre_tool.add_argument("--semantic-verifier", choices=["none", "openai"], default="none")
    pre_tool.add_argument("--semantic-model", default=None)
    pre_tool.add_argument("--strict-validation", action="store_true")
    pre_tool.add_argument("--validate-only", action="store_true")
    pre_tool.add_argument("--audit-log", default=None)
    pre_tool.set_defaults(func=command_pre_tool_check)

    audit = subparsers.add_parser("audit-summary", help="Summarize a redacted AANA audit JSONL file.")
    audit.add_argument("--audit-log", required=True)
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=command_audit_summary)

    evidence = subparsers.add_parser("evidence-pack", help="Summarize and validate the AANA production-candidate evidence pack.")
    evidence.add_argument("--manifest", default=DEFAULT_EVIDENCE_PACK)
    evidence.add_argument("--require-existing-artifacts", action="store_true")
    evidence.set_defaults(func=command_evidence_pack)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"aana: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
