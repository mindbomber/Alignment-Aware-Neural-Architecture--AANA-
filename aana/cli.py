"""Runtime-focused command line interface for the public AANA package."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import sys
import time

from aana.sdk import architecture_decision, with_architecture_decision
from eval_pipeline import agent_api
from eval_pipeline import aix_audit
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2, validate_event as validate_tool_precheck_event
from eval_pipeline.production_candidate_evidence_pack import (
    load_manifest as load_evidence_pack_manifest,
    validate_production_candidate_evidence_pack,
)
from eval_pipeline.semantic_verifier import build_semantic_verifier


ROOT = pathlib.Path.cwd()
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_EVIDENCE_PACK = ROOT / "examples" / "production_candidate_evidence_pack.json"
PUBLIC_ARCHITECTURE_CLAIM = "AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept."


def _check_status(name: str, status: str, message: str, details: dict | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_json(path: str | pathlib.Path) -> dict:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _provider_status() -> dict:
    provider = os.environ.get("AANA_PROVIDER", "openai").strip().lower()
    if provider == "openai":
        ready = bool(os.environ.get("OPENAI_API_KEY"))
        return _check_status(
            "provider_config",
            "pass" if ready else "warn",
            "OpenAI-compatible provider is configured." if ready else "No live OpenAI API key found. Local demos still work.",
            {
                "provider": provider,
                "api_key_present": ready,
                "custom_endpoint_configured": bool(os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")),
            },
        )
    if provider == "anthropic":
        ready = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return _check_status(
            "provider_config",
            "pass" if ready else "warn",
            "Anthropic provider is configured." if ready else "No live Anthropic API key found. Local demos still work.",
            {
                "provider": provider,
                "api_key_present": ready,
                "custom_endpoint_configured": bool(os.environ.get("ANTHROPIC_MESSAGES_URL") or os.environ.get("ANTHROPIC_BASE_URL")),
            },
        )
    return _check_status(
        "provider_config",
        "fail",
        f"Unsupported AANA_PROVIDER {provider!r}. Supported providers: openai, anthropic.",
        {"provider": provider},
    )


def _doctor_report(gallery_path: str | pathlib.Path = DEFAULT_GALLERY) -> dict:
    checks = []
    gallery_path = pathlib.Path(gallery_path)
    python_ok = sys.version_info >= (3, 10)
    checks.append(
        _check_status(
            "python",
            "pass" if python_ok else "fail",
            f"Python {platform.python_version()} detected.",
            {"executable": sys.executable, "requires": ">=3.10"},
        )
    )
    checks.append(
        _check_status(
            "runtime_cli",
            "pass",
            "AANA runtime CLI is importable.",
            {"root": str(ROOT), "module": __name__},
        )
    )
    if not gallery_path.exists():
        checks.append(
            _check_status(
                "adapter_gallery",
                "warn",
                "Adapter gallery not found; skipping repo onboarding gallery check for packaged runtime install.",
                {"gallery_path": str(gallery_path), "skipped": True},
            )
        )
        checks.append(
            _check_status(
                "agent_event_examples",
                "warn",
                "Agent event examples not found; skipping repo onboarding examples check for packaged runtime install.",
                {"gallery_path": str(gallery_path), "skipped": True},
            )
        )
    else:
        try:
            gallery = agent_api.load_gallery(gallery_path)
            entries = agent_api.gallery_entries(gallery)
            checks.append(
                _check_status(
                    "adapter_gallery",
                    "pass" if entries else "fail",
                    f"Adapter gallery loaded with {len(entries)} adapter(s)." if entries else "Adapter gallery has no adapters.",
                    {"adapter_ids": [entry.get("id") for entry in entries]},
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(_check_status("adapter_gallery", "fail", str(exc)))
        try:
            agent_examples = agent_api.run_agent_event_examples(gallery_path=gallery_path)
            checks.append(
                _check_status(
                    "agent_event_examples",
                    "pass" if agent_examples["valid"] else "fail",
                    f"{agent_examples['count']} agent event examples checked.",
                    {"checked_examples": agent_examples["checked_examples"]},
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(_check_status("agent_event_examples", "fail", str(exc)))
    schemas = agent_api.schema_catalog()
    required_schemas = {
        "agent_event",
        "agent_check_result",
        "workflow_request",
        "workflow_batch_request",
        "workflow_result",
        "workflow_batch_result",
    }
    schema_ok = required_schemas.issubset(schemas)
    checks.append(
        _check_status(
            "agent_schemas",
            "pass" if schema_ok else "fail",
            "Agent and workflow schemas are available." if schema_ok else "Agent or workflow schemas are incomplete.",
            {"schemas": sorted(schemas.keys())},
        )
    )
    checks.append(_provider_status())
    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    return {
        "valid": not failed,
        "summary": {
            "status": "pass" if not failed else "fail",
            "checks": len(checks),
            "failures": len(failed),
            "warnings": len(warnings),
        },
        "checks": checks,
    }


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


def command_doctor(args: argparse.Namespace) -> int:
    report = _doctor_report(gallery_path=args.gallery)
    if args.json:
        _print_json(report)
    else:
        summary = report["summary"]
        print(f"AANA doctor: {summary['status']} ({summary['failures']} failure(s), {summary['warnings']} warning(s)).")
        for check in report["checks"]:
            print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
    return 0 if report["valid"] else 1


def command_list(args: argparse.Namespace) -> int:
    gallery = agent_api.load_gallery(args.gallery)
    rows = []
    for entry in agent_api.gallery_entries(gallery):
        rows.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "status": entry.get("status"),
                "best_for": entry.get("best_for", []),
                "adapter_path": entry.get("adapter_path"),
            }
        )
    if args.json:
        _print_json({"adapters": rows})
        return 0

    print("Available AANA adapters:")
    for row in rows:
        best_for = ", ".join(row["best_for"])
        print(f"- {row['id']}: {row['title']} ({row['status']})")
        print(f"  Best for: {best_for}")
        print(f"  File: {row['adapter_path']}")
    return 0


def _workflow_request_from_gallery_entry(entry: dict) -> dict:
    return {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "workflow_id": f"gallery-{entry['id']}",
        "adapter": entry["id"],
        "request": entry["prompt"],
        "candidate": entry.get("bad_candidate"),
        "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
        "metadata": {
            "surface": "aana_cli_run",
            "gallery_title": entry.get("title"),
            "gallery_status": entry.get("status"),
        },
    }


def command_run(args: argparse.Namespace) -> int:
    gallery = agent_api.load_gallery(args.gallery)
    entry = agent_api.find_entry(gallery, args.adapter_id)
    result = agent_api.check_workflow_request(
        _workflow_request_from_gallery_entry(entry),
        gallery_path=args.gallery,
    )
    _print_json(result)
    return 0 if result.get("gate_decision") == "pass" else 1


def command_run_agent_examples(args: argparse.Namespace) -> int:
    report = agent_api.run_agent_event_examples(events_dir=args.events_dir, gallery_path=args.gallery)
    if args.json:
        _print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Agent event examples are {status}: {report['count']} checked.")
        for item in report["checked_examples"]:
            expectation = "ok" if item["passed_expectations"] else "unexpected"
            print(
                f"- {item['event_id']}: adapter={item['adapter_id']} "
                f"candidate_gate={item['candidate_gate']} gate={item['gate_decision']} "
                f"action={item['recommended_action']} aix={item.get('aix_decision')} "
                f"expectations={expectation}"
            )
    return 0 if report["valid"] else 1


def command_scaffold_agent_event(args: argparse.Namespace) -> int:
    output_path = pathlib.Path(args.output_dir) / f"{args.adapter_id}.json"
    if args.dry_run:
        event = agent_api.build_agent_event_from_gallery(args.adapter_id, gallery_path=args.gallery, agent=args.agent)
        _print_json(
            {
                "dry_run": True,
                "would_create": {"event": str(output_path)},
                "event_preview": event,
                "next_steps": [
                    f"aana scaffold-agent-event {args.adapter_id} --output-dir {args.output_dir}",
                    f"aana agent-check --event {output_path}",
                ],
            }
        )
        return 0

    created = agent_api.scaffold_agent_event(
        args.adapter_id,
        output_dir=args.output_dir,
        gallery_path=args.gallery,
        agent=args.agent,
        force=args.force,
    )
    _print_json({"created": created})
    return 0


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


def command_workflow_check(args: argparse.Namespace) -> int:
    started_at = time.perf_counter()
    workflow_request = _load_json(args.workflow)
    result = agent_api.check_workflow_request(workflow_request, gallery_path=args.gallery)
    result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    if args.shadow_mode:
        result = agent_api.apply_shadow_mode(result)
    if args.audit_log:
        agent_api.append_audit_record(args.audit_log, agent_api.audit_workflow_check(workflow_request, result))
    _print_json(result)
    return 0 if args.shadow_mode or result.get("gate_decision") == "pass" else 1


def command_workflow_batch(args: argparse.Namespace) -> int:
    started_at = time.perf_counter()
    batch_request = _load_json(args.batch)
    result = agent_api.check_workflow_batch(batch_request, gallery_path=args.gallery)
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    for item in result.get("results", []) if isinstance(result, dict) else []:
        if isinstance(item, dict):
            item.setdefault("audit_metadata", {})["latency_ms"] = latency_ms
    if args.shadow_mode:
        result = agent_api.apply_shadow_mode(result)
    if args.audit_log:
        record = agent_api.audit_workflow_batch(batch_request, result)
        for item in record.get("records", []):
            agent_api.append_audit_record(args.audit_log, item)
    _print_json(result)
    return 0 if args.shadow_mode or result.get("summary", {}).get("failed", 1) == 0 else 1


def command_aix_audit(args: argparse.Namespace) -> int:
    report = aix_audit.run_enterprise_ops_aix_audit(
        output_dir=args.output_dir,
        batch_path=args.batch,
        kit_dir=args.kit_dir,
        gallery_path=args.gallery,
        append=args.append,
        shadow_mode=not args.enforce_mode,
    )
    if args.json:
        _print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    print(f"AANA AIx Audit ({report['product_bundle']}): {'PASS' if report['valid'] else 'FAIL'}")
    print(f"- Recommendation: {report['deployment_recommendation']}")
    print(f"- Workflows: {summary['workflow_count']}")
    print(f"- Audit records: {summary['audit_records']}")
    print(f"- AIx report: {summary['aix_report_md']}")
    print(f"- Report JSON: {summary['aix_report_json']}")
    print(f"- Enterprise dashboard: {summary['enterprise_dashboard']}")
    return 0 if report["valid"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "AANA runtime CLI. Research, benchmark, and HF experiment tooling stays "
            "repo-local under scripts/ and is not installed as public package commands."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check local AANA runtime readiness.")
    doctor.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    doctor.add_argument("--json", action="store_true", help="Emit JSON.")
    doctor.set_defaults(func=command_doctor)

    list_parser = subparsers.add_parser("list", help="List gallery adapters.")
    list_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    list_parser.set_defaults(func=command_list)

    run_parser = subparsers.add_parser("run", help="Run a gallery adapter by id.")
    run_parser.add_argument("adapter_id", help="Gallery adapter id.")
    run_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    run_parser.set_defaults(func=command_run)

    run_examples = subparsers.add_parser("run-agent-examples", help="Run executable Agent Event examples.")
    run_examples.add_argument("--events-dir", default=agent_api.DEFAULT_AGENT_EVENTS_DIR, help="Directory of Agent Event JSON files.")
    run_examples.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    run_examples.add_argument("--json", action="store_true", help="Emit JSON.")
    run_examples.set_defaults(func=command_run_agent_examples)

    scaffold_event = subparsers.add_parser("scaffold-agent-event", help="Create a starter Agent Event JSON from a gallery adapter.")
    scaffold_event.add_argument("adapter_id", help="Gallery adapter id.")
    scaffold_event.add_argument("--output-dir", default=agent_api.DEFAULT_AGENT_EVENTS_DIR, help="Output directory for the event JSON.")
    scaffold_event.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    scaffold_event.add_argument("--agent", default="openclaw", help="Agent/runtime label to include in the event.")
    scaffold_event.add_argument("--dry-run", action="store_true", help="Preview the event without writing a file.")
    scaffold_event.add_argument("--force", action="store_true", help="Overwrite an existing event file.")
    scaffold_event.set_defaults(func=command_scaffold_agent_event)

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

    workflow = subparsers.add_parser("workflow-check", help="Check a Workflow Contract request.")
    workflow.add_argument("--workflow", required=True, help="Workflow Contract request JSON.")
    workflow.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    workflow.add_argument("--shadow-mode", action="store_true")
    workflow.add_argument("--audit-log", default=None)
    workflow.set_defaults(func=command_workflow_check)

    workflow_batch = subparsers.add_parser("workflow-batch", help="Check a Workflow Contract batch request.")
    workflow_batch.add_argument("--batch", required=True, help="Workflow Contract batch JSON.")
    workflow_batch.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    workflow_batch.add_argument("--shadow-mode", action="store_true")
    workflow_batch.add_argument("--audit-log", default=None)
    workflow_batch.set_defaults(func=command_workflow_batch)

    aix_audit_parser = subparsers.add_parser("aix-audit", help="Run the enterprise-ops AANA AIx Audit.")
    aix_audit_parser.add_argument("--batch", default=None, help="Optional Workflow Contract batch JSON.")
    aix_audit_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    aix_audit_parser.add_argument(
        "--kit-dir",
        default=ROOT / "examples" / "starter_pilot_kits" / "enterprise",
        help="Enterprise starter kit directory used when --batch is not provided.",
    )
    aix_audit_parser.add_argument(
        "--output-dir",
        default=ROOT / "eval_outputs" / "aix_audit" / "enterprise_ops_pilot",
        help="Directory for generated AIx audit artifacts.",
    )
    aix_audit_parser.add_argument("--append", action="store_true")
    aix_audit_parser.add_argument("--enforce-mode", action="store_true")
    aix_audit_parser.add_argument("--json", action="store_true")
    aix_audit_parser.set_defaults(func=command_aix_audit)

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
