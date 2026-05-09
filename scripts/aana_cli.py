#!/usr/bin/env python
"""Small command hub for trying and extending AANA adapters."""

import argparse
import json
import os
import pathlib
import platform
import subprocess
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import new_adapter
import run_adapter
import validate_adapter
import validate_adapter_gallery
from eval_pipeline import (
    civic_family,
    common,
    contract_freeze,
    bundle_certification,
    enterprise_family,
    evidence_integrations,
    personal_family,
    pilot_certification,
    production,
    production_certification,
    support_aix_calibration,
)
from eval_pipeline import agent_api
from eval_pipeline.production_candidate_evidence_pack import (
    load_manifest as load_evidence_pack_manifest,
    validate_production_candidate_evidence_pack,
)
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2, validate_event as validate_tool_precheck_event
from aana.sdk import architecture_decision, with_architecture_decision


DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_EVIDENCE_PACK = ROOT / "examples" / "production_candidate_evidence_pack.json"
CLI_CONTRACT_VERSION = "0.1"
EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_CODE_CONTRACT = {
    str(EXIT_OK): "Command completed successfully.",
    str(EXIT_VALIDATION): "The command ran and found validation, gate, release, or policy failures.",
    str(EXIT_USAGE): "The command could not run because inputs, paths, JSON, or arguments were invalid.",
}
READ_FILE_ARGS_BY_COMMAND = {
    "run-file": ["adapter", "candidate_file"],
    "agent-check": ["event", "evidence_registry"],
    "pre-tool-check": ["event"],
    "evidence-pack": ["manifest"],
    "workflow-check": ["workflow", "evidence_registry"],
    "workflow-batch": ["batch", "evidence_registry"],
    "validate-workflow": ["workflow"],
    "validate-workflow-batch": ["batch"],
    "validate-evidence-registry": ["evidence_registry"],
    "evidence-integrations": ["evidence_registry", "mock_fixtures"],
    "validate-workflow-evidence": ["workflow", "evidence_registry"],
    "validate-event": ["event", "evidence_registry"],
    "audit-validate": ["audit_log"],
    "audit-summary": ["audit_log"],
    "audit-metrics": ["audit_log"],
    "audit-drift": ["audit_log", "baseline_metrics"],
    "audit-reviewer-report": ["audit_log", "metrics", "drift_report", "manifest"],
    "audit-manifest": ["audit_log", "previous_manifest"],
    "audit-verify": ["manifest"],
    "production-preflight": ["deployment_manifest", "evidence_registry", "observability_policy"],
    "pilot-certify": ["gallery", "evidence_registry"],
    "certify-bundle": ["gallery", "evidence_registry", "mock_fixtures", "certification_policy"],
    "enterprise-certify": ["gallery", "evidence_registry", "mock_fixtures", "certification_policy"],
    "personal-certify": ["gallery", "evidence_registry", "mock_fixtures", "certification_policy"],
    "civic-certify": ["gallery", "evidence_registry", "mock_fixtures", "certification_policy"],
    "production-certify": [
        "certification_policy",
        "deployment_manifest",
        "governance_policy",
        "evidence_registry",
        "observability_policy",
        "audit_log",
        "external_evidence",
    ],
    "contract-freeze": ["gallery", "evidence_registry"],
    "validate-deployment": ["deployment_manifest"],
    "validate-governance": ["governance_policy"],
    "validate-observability": ["observability_policy"],
    "release-check": [
        "deployment_manifest",
        "governance_policy",
        "evidence_registry",
        "observability_policy",
        "audit_log",
    ],
    "validate-adapter": ["adapter"],
}
READ_DIR_ARGS_BY_COMMAND = {
    "run-agent-examples": ["events_dir"],
}


class CliError(RuntimeError):
    def __init__(self, message, exit_code=EXIT_USAGE, details=None):
        super().__init__(message)
        self.exit_code = exit_code
        self.details = details or {}


def load_gallery(path=DEFAULT_GALLERY):
    return validate_adapter_gallery.load_gallery(path)


def gallery_entries(gallery):
    return gallery.get("adapters", []) if isinstance(gallery.get("adapters"), list) else []


def find_entry(gallery, adapter_id):
    for entry in gallery_entries(gallery):
        if entry.get("id") == adapter_id:
            return entry
    available = ", ".join(entry.get("id", "") for entry in gallery_entries(gallery))
    raise ValueError(f"Unknown adapter id: {adapter_id}. Available adapters: {available}.")


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cli_command_matrix():
    return [
        {
            "command": "list",
            "category": "discovery",
            "json_output": True,
            "reads": ["--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py list --json",
        },
        {
            "command": "aix-tuning",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py aix-tuning --json",
        },
        {
            "command": "support-aix-calibration",
            "category": "readiness",
            "json_output": True,
            "reads": ["--support-fixtures", "--calibration-fixtures"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py support-aix-calibration --json",
        },
        {
            "command": "run",
            "category": "adapter",
            "json_output": True,
            "public_api": "workflow_contract",
            "reads": ["--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py run support_reply",
        },
        {
            "command": "run-file",
            "category": "adapter",
            "json_output": True,
            "public_api": False,
            "reads": ["--adapter", "--candidate-file"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py run-file --adapter examples/support_reply_adapter.json --prompt \"...\" --candidate \"...\"",
        },
        {
            "command": "agent-check",
            "category": "agent",
            "json_output": True,
            "public_api": "agent_event_contract",
            "reads": ["--event", "--evidence-registry", "--gallery", "--shadow-mode"],
            "writes": ["--audit-log"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/aana-audit.jsonl --shadow-mode",
        },
        {
            "command": "workflow-check",
            "category": "workflow",
            "json_output": True,
            "public_api": "workflow_contract",
            "reads": ["--workflow", "--evidence-registry", "--gallery", "--shadow-mode"],
            "writes": ["--audit-log"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json",
        },
        {
            "command": "workflow-batch",
            "category": "workflow",
            "json_output": True,
            "public_api": "workflow_contract",
            "reads": ["--batch", "--evidence-registry", "--gallery", "--shadow-mode"],
            "writes": ["--audit-log"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/aana-audit.jsonl",
        },
        {
            "command": "validate-workflow",
            "category": "validation",
            "json_output": True,
            "reads": ["--workflow"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json --json",
        },
        {
            "command": "validate-workflow-batch",
            "category": "validation",
            "json_output": True,
            "reads": ["--batch"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json --json",
        },
        {
            "command": "validate-evidence-registry",
            "category": "validation",
            "json_output": True,
            "reads": ["--evidence-registry"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-evidence-registry --evidence-registry examples/evidence_registry.json --json",
        },
        {
            "command": "evidence-integrations",
            "category": "readiness",
            "json_output": True,
            "reads": ["--evidence-registry", "--mock-fixtures"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json --json",
        },
        {
            "command": "connector-marketplace",
            "category": "readiness",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py connector-marketplace --json",
        },
        {
            "command": "validate-workflow-evidence",
            "category": "validation",
            "json_output": True,
            "reads": ["--workflow", "--evidence-registry"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-workflow-evidence --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured --json",
        },
        {
            "command": "validate-event",
            "category": "validation",
            "json_output": True,
            "reads": ["--event", "--evidence-registry"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json --json",
        },
        {
            "command": "agent-schema",
            "category": "contract",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py agent-schema all",
        },
        {
            "command": "workflow-schema",
            "category": "contract",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py workflow-schema all",
        },
        {
            "command": "run-agent-examples",
            "category": "agent",
            "json_output": True,
            "reads": ["--events-dir", "--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py run-agent-examples --json",
        },
        {
            "command": "scaffold-agent-event",
            "category": "scaffold",
            "json_output": True,
            "reads": ["--gallery"],
            "writes": ["--output-dir"],
            "dry_run": True,
            "example": "python scripts/aana_cli.py scaffold-agent-event support_reply --dry-run",
        },
        {
            "command": "policy-presets",
            "category": "agent",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py policy-presets --json",
        },
        {
            "command": "audit-validate",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/aana-audit.jsonl --json",
        },
        {
            "command": "audit-summary",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl --json",
        },
        {
            "command": "audit-metrics",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log"],
            "writes": ["--output"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-metrics.json",
        },
        {
            "command": "audit-drift",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log", "--baseline-metrics"],
            "writes": ["--output"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-drift --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-aix-drift.json",
        },
        {
            "command": "audit-reviewer-report",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log", "--metrics", "--drift-report", "--manifest"],
            "writes": ["--output"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-reviewer-report --audit-log eval_outputs/audit/aana-audit.jsonl --metrics eval_outputs/audit/aana-metrics.json --drift-report eval_outputs/audit/aana-aix-drift.json --output eval_outputs/audit/aana-reviewer-report.md",
        },
        {
            "command": "audit-manifest",
            "category": "audit",
            "json_output": True,
            "reads": ["--audit-log", "--previous-manifest"],
            "writes": ["--output"],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-manifest --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/manifests/aana-audit-integrity.json",
        },
        {
            "command": "audit-verify",
            "category": "audit",
            "json_output": True,
            "reads": ["--manifest"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-audit-integrity.json",
        },
        {
            "command": "pilot-certify",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery", "--evidence-registry"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py pilot-certify --evidence-registry examples/evidence_registry.json --json",
        },
        {
            "command": "certify-bundle",
            "category": "readiness",
            "json_output": True,
            "reads": ["bundle_id", "--gallery", "--evidence-registry", "--mock-fixtures", "--certification-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py certify-bundle enterprise --json",
        },
        {
            "command": "enterprise-certify",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery", "--evidence-registry", "--mock-fixtures", "--certification-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py enterprise-certify --json",
        },
        {
            "command": "personal-certify",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery", "--evidence-registry", "--mock-fixtures", "--certification-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py personal-certify --json",
        },
        {
            "command": "civic-certify",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery", "--evidence-registry", "--mock-fixtures", "--certification-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py civic-certify --json",
        },
        {
            "command": "production-preflight",
            "category": "readiness",
            "json_output": True,
            "reads": ["--deployment-manifest", "--evidence-registry", "--observability-policy", "--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py production-preflight --deployment-manifest examples/production_deployment_template.json --evidence-registry examples/evidence_registry.json --json",
        },
        {
            "command": "production-certify",
            "category": "readiness",
            "json_output": True,
            "reads": [
                "--certification-policy",
                "--deployment-manifest",
                "--governance-policy",
                "--evidence-registry",
                "--observability-policy",
                "--audit-log",
                "--external-evidence",
            ],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py production-certify --certification-policy examples/production_certification_template.json --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy.json --audit-log path/to/shadow-audit.jsonl --external-evidence path/to/external-production-evidence.json --json",
        },
        {
            "command": "readiness-matrix",
            "category": "readiness",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py readiness-matrix --json",
        },
        {
            "command": "contract-freeze",
            "category": "contract",
            "json_output": True,
            "reads": ["--gallery", "--evidence-registry"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py contract-freeze --json",
        },
        {
            "command": "validate-deployment",
            "category": "validation",
            "json_output": True,
            "reads": ["--deployment-manifest"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-deployment --deployment-manifest examples/production_deployment_template.json --json",
        },
        {
            "command": "validate-governance",
            "category": "validation",
            "json_output": True,
            "reads": ["--governance-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-governance --governance-policy examples/human_governance_policy_template.json --json",
        },
        {
            "command": "validate-observability",
            "category": "validation",
            "json_output": True,
            "reads": ["--observability-policy"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-observability --observability-policy examples/observability_policy.json --json",
        },
        {
            "command": "release-check",
            "category": "readiness",
            "json_output": True,
            "reads": ["--deployment-manifest", "--governance-policy", "--evidence-registry", "--observability-policy", "--audit-log", "--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py release-check --skip-local-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy.json --json",
        },
        {
            "command": "doctor",
            "category": "readiness",
            "json_output": True,
            "reads": ["--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py doctor --json",
        },
        {
            "command": "validate-adapter",
            "category": "validation",
            "json_output": True,
            "reads": ["adapter"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-adapter examples/support_reply_adapter.json --json",
        },
        {
            "command": "validate-gallery",
            "category": "validation",
            "json_output": True,
            "reads": ["--gallery"],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py validate-gallery --run-examples --json",
        },
        {
            "command": "scaffold",
            "category": "scaffold",
            "json_output": True,
            "reads": [],
            "writes": ["--output-dir"],
            "dry_run": True,
            "example": "python scripts/aana_cli.py scaffold \"insurance claim triage\" --output-dir examples --dry-run",
        },
        {
            "command": "cli-contract",
            "category": "contract",
            "json_output": True,
            "reads": [],
            "writes": [],
            "dry_run": False,
            "example": "python scripts/aana_cli.py cli-contract --json",
        },
    ]


def command_cli_contract(args):
    contract = {
        "cli_contract_version": CLI_CONTRACT_VERSION,
        "exit_codes": EXIT_CODE_CONTRACT,
        "error_contract": {
            "ok": False,
            "error": {
                "type": "CliError",
                "message": "Human-readable error.",
                "details": {"argument": "--event", "path": "missing.json"},
            },
            "exit_code": EXIT_USAGE,
        },
        "commands": cli_command_matrix(),
    }
    if args.json:
        print_json(contract)
        return EXIT_OK

    print(f"AANA CLI contract v{CLI_CONTRACT_VERSION}")
    print("Exit codes:")
    for code, description in EXIT_CODE_CONTRACT.items():
        print(f"- {code}: {description}")
    print("Commands:")
    for command in contract["commands"]:
        print(
            f"- {command['command']}: category={command['category']} "
            f"json={command['json_output']} dry_run={command['dry_run']}"
        )
    return EXIT_OK


def print_cli_error(error, json_output=False):
    if json_output:
        print_json(
            {
                "cli_contract_version": CLI_CONTRACT_VERSION,
                "ok": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                    "details": error.details,
                },
                "exit_code": error.exit_code,
            }
        )
        return
    print(f"aana_cli failed: {error}", file=sys.stderr)


def option_name(argument_name):
    return argument_name if argument_name == "adapter" else f"--{argument_name.replace('_', '-')}"


def validate_existing_file(argument_name, value):
    path = pathlib.Path(value)
    if not path.exists():
        raise CliError(
            f"{argument_name.replace('_', '-')} path does not exist: {value}",
            details={"argument": option_name(argument_name), "path": str(value)},
        )
    if not path.is_file():
        raise CliError(
            f"{argument_name.replace('_', '-')} path is not a file: {value}",
            details={"argument": option_name(argument_name), "path": str(value)},
        )


def validate_existing_dir(argument_name, value):
    path = pathlib.Path(value)
    if not path.exists():
        raise CliError(
            f"{argument_name.replace('_', '-')} directory does not exist: {value}",
            details={"argument": option_name(argument_name), "path": str(value)},
        )
    if not path.is_dir():
        raise CliError(
            f"{argument_name.replace('_', '-')} path is not a directory: {value}",
            details={"argument": option_name(argument_name), "path": str(value)},
        )


def validate_cli_paths(args):
    command = getattr(args, "command", None)
    for argument_name in READ_FILE_ARGS_BY_COMMAND.get(command, []):
        value = getattr(args, argument_name, None)
        if value:
            validate_existing_file(argument_name, value)
    for argument_name in READ_DIR_ARGS_BY_COMMAND.get(command, []):
        value = getattr(args, argument_name, None)
        if value:
            validate_existing_dir(argument_name, value)


def command_list(args):
    gallery = load_gallery(args.gallery)
    rows = []
    for entry in gallery_entries(gallery):
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
        print_json({"adapters": rows})
        return 0

    print("Available AANA adapters:")
    for row in rows:
        best_for = ", ".join(row["best_for"])
        print(f"- {row['id']}: {row['title']} ({row['status']})")
        print(f"  Best for: {best_for}")
        print(f"  File: {row['adapter_path']}")
    return 0


def adapter_aix_tuning_report(gallery):
    adapters = []
    all_issues = []
    tier_counts = {}
    failing = 0
    for entry in gallery_entries(gallery):
        adapter_path = ROOT / str(entry.get("adapter_path", ""))
        adapter = validate_adapter.load_adapter(adapter_path)
        config = adapter.get("aix", {}) if isinstance(adapter.get("aix"), dict) else {}
        tier = config.get("risk_tier", "unspecified")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        issues = [
            issue
            for issue in validate_adapter.validate_adapter(adapter)["issues"]
            if issue.get("path", "").startswith("aix")
        ]
        issues.extend(validate_adapter.aix_tier_issues(config))
        if tier == "unspecified":
            validate_adapter.add_issue(
                issues,
                "warning",
                "aix.risk_tier",
                "AIx risk_tier is missing; tuning cannot be audited against a declared tier.",
            )
        meets_tier = not issues
        if not meets_tier:
            failing += 1
        for issue in issues:
            all_issues.append({"adapter_id": entry.get("id"), "adapter_path": entry.get("adapter_path"), **issue})
        adapters.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "adapter_path": entry.get("adapter_path"),
                "risk_tier": tier,
                "beta": config.get("beta"),
                "layer_weights": config.get("layer_weights", {}),
                "thresholds": config.get("thresholds", {}),
                "meets_tier": meets_tier,
                "issues": issues,
            }
        )
    return {
        "valid": failing == 0,
        "adapter_count": len(adapters),
        "failing_count": failing,
        "risk_tier_counts": tier_counts,
        "issues": all_issues,
        "adapters": adapters,
    }


def command_aix_tuning(args):
    gallery = load_gallery(args.gallery)
    report = adapter_aix_tuning_report(gallery)
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1

    status = "valid" if report["valid"] else "invalid"
    print(f"AANA adapter AIx tuning report: {status} ({report['adapter_count']} adapter(s)).")
    print("Risk tiers:")
    for tier, count in sorted(report["risk_tier_counts"].items()):
        print(f"- {tier}: {count}")
    print("Adapters:")
    for item in report["adapters"]:
        thresholds = item["thresholds"]
        print(
            f"- {item['id']}: tier={item['risk_tier']} beta={item['beta']} "
            f"accept={thresholds.get('accept')} revise={thresholds.get('revise')} "
            f"defer={thresholds.get('defer')} meets_tier={item['meets_tier']}"
        )
        for issue in item["issues"]:
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_support_aix_calibration(args):
    report = support_aix_calibration.evaluate_support_calibration(
        support_fixture_path=args.support_fixtures,
        calibration_fixture_path=args.calibration_fixtures,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1

    status = "valid" if report["valid"] else "invalid"
    metrics = report["metrics"]
    print(f"AANA support AIx calibration report: {status} ({metrics['case_count']} case(s)).")
    print(f"- passed: {metrics['passed_count']}/{metrics['case_count']}")
    print(f"- over-acceptance: {metrics['over_acceptance_count']} ({metrics['over_acceptance_rate']})")
    print(f"- over-refusal: {metrics['over_refusal_count']} ({metrics['over_refusal_rate']})")
    print(f"- correction success: {metrics['correction_success_rate']}")
    print(f"- human-review precision: {metrics['human_review_precision']}")
    print(f"- false blocker rate: {metrics['false_blocker_rate']}")
    print(f"- evidence-missing behavior: {metrics['evidence_missing_behavior_rate']}")
    for item in report["cases"]:
        observed = item["observed"]
        print(
            f"- {item['id']}: passed={item['passed']} tier={item['risk_tier']} "
            f"action={observed['recommended_action']} candidate_gate={observed['candidate_gate']} "
            f"candidate_aix={observed['candidate_aix_score']}"
        )
    return 0 if report["valid"] else 1


def workflow_request_from_gallery_entry(entry):
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


def run_entry(entry, gallery_path=DEFAULT_GALLERY):
    return agent_api.check_workflow_request(
        workflow_request_from_gallery_entry(entry),
        gallery_path=gallery_path,
    )


def command_run(args):
    gallery = load_gallery(args.gallery)
    entry = find_entry(gallery, args.adapter_id)
    result = run_entry(entry, gallery_path=args.gallery)
    print_json(result)
    return 0 if result.get("gate_decision") == "pass" else 1


def command_run_file(args):
    adapter = run_adapter.load_adapter(args.adapter)
    candidate = args.candidate
    if args.candidate_file:
        candidate = pathlib.Path(args.candidate_file).read_text(encoding="utf-8")
    result = run_adapter.run_adapter(adapter, args.prompt, candidate)
    result = {
        **result,
        "runtime_boundary": {
            "public_api": False,
            "entrypoint": "legacy_adapter_runner",
            "recommended_entrypoint": "workflow-check",
            "note": "run-file executes an adapter JSON file directly and is intended for adapter development diagnostics.",
        },
    }
    print_json(result)
    return 0 if result.get("gate_decision") in {"pass", "needs_adapter_implementation"} else 1


def command_agent_check(args):
    started_at = time.perf_counter()
    event = agent_api.load_json_file(args.event)
    if args.evidence_registry or args.require_structured_evidence:
        registry = agent_api.load_evidence_registry(args.evidence_registry) if args.evidence_registry else None
        report = agent_api.validate_event(
            event,
            evidence_registry=registry,
            require_structured_evidence=args.require_structured_evidence,
        )
        if not report["valid"]:
            print_json({"event_validation": report})
            return 1
    response = agent_api.check_event(event, gallery_path=args.gallery, adapter_id=args.adapter_id)
    response.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    if args.shadow_mode:
        response = agent_api.apply_shadow_mode(response)
    if args.audit_log:
        record = agent_api.audit_event_check(event, response)
        agent_api.append_audit_record(args.audit_log, record)
    else:
        record = agent_api.audit_event_check(event, response)
    response = with_architecture_decision(response, event, audit_record=record)
    print_json(response)
    return 0 if args.shadow_mode or response["gate_decision"] == "pass" else 1


def command_pre_tool_check(args):
    started_at = time.perf_counter()
    event = agent_api.load_json_file(args.event)
    validation_errors = validate_tool_precheck_event(event)
    if args.validate_only:
        response = {
            "valid": not validation_errors,
            "errors": validation_errors,
            "schema_version": "aana.agent_tool_precheck.v1",
        }
        print_json(response)
        return 0 if response["valid"] else 1
    if validation_errors and args.strict_validation:
        print_json(
            {
                "valid": False,
                "errors": validation_errors,
                "schema_version": "aana.agent_tool_precheck.v1",
                "architecture_decision": architecture_decision(
                    {
                        "gate_decision": "fail",
                        "recommended_action": "refuse",
                        "hard_blockers": ["schema_validation_failed"],
                        "aix": {"score": 0.0, "decision": "refuse", "hard_blockers": ["schema_validation_failed"]},
                    },
                    event,
                ),
            }
        )
        return 1
    result = gate_pre_tool_call_v2(event) if args.gate_version == "v2" else gate_pre_tool_call(event)
    result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    response = with_architecture_decision(result, event)
    print_json(response)
    return 0 if response.get("gate_decision") == "pass" else 1


def command_evidence_pack(args):
    manifest = load_evidence_pack_manifest(args.manifest)
    report = validate_production_candidate_evidence_pack(
        manifest,
        root=ROOT,
        require_existing_artifacts=args.require_existing_artifacts,
    )
    response = {
        "architecture_claim": "AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable.",
        "claim_boundary": manifest.get("claim_boundary", {}),
        "evidence_status": manifest.get("evidence_status"),
        "report_path": manifest.get("report_path"),
        "required_artifacts": manifest.get("required_artifacts", []),
        "limitations": manifest.get("limitations", {}),
        "validation": report,
    }
    if args.json:
        print_json(response)
    else:
        print("AANA evidence pack")
        print(f"- architecture_claim: {response['architecture_claim']}")
        print(f"- production_candidate_layer: {response['claim_boundary'].get('production_candidate_layer')}")
        print(f"- not_proven_engine: {response['claim_boundary'].get('not_proven_engine')}")
        print(f"- evidence_status: {response['evidence_status']}")
        print(f"- report_path: {response['report_path']}")
        print(f"- artifacts: {len(response['required_artifacts'])}")
        print(f"- validation: {'pass' if report['valid'] else 'block'} ({report['errors']} errors, {report['warnings']} warnings)")
        if report["issues"]:
            for issue in report["issues"]:
                print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_workflow_check(args):
    started_at = time.perf_counter()
    if args.workflow:
        workflow_request = agent_api.load_json_file(args.workflow)
        if args.evidence_registry:
            registry = agent_api.load_evidence_registry(args.evidence_registry)
            evidence_report = agent_api.validate_workflow_evidence(
                workflow_request,
                registry,
                require_structured=args.require_structured_evidence,
            )
            if not evidence_report["valid"]:
                print_json({"evidence_validation": evidence_report})
                return 1
        result = agent_api.check_workflow_request(workflow_request, gallery_path=args.gallery)
        result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
        if args.shadow_mode:
            result = agent_api.apply_shadow_mode(result)
        if args.audit_log:
            record = agent_api.audit_workflow_check(workflow_request, result)
            agent_api.append_audit_record(args.audit_log, record)
        print_json(result)
        return 0 if args.shadow_mode or result["gate_decision"] == "pass" else 1

    evidence = list(args.evidence or [])
    constraints = list(args.constraint or [])
    workflow_request = {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "workflow_id": args.workflow_id,
        "adapter": args.adapter,
        "request": args.request,
        "candidate": args.candidate,
        "evidence": evidence,
        "constraints": constraints,
    }
    if args.evidence_registry:
        registry = agent_api.load_evidence_registry(args.evidence_registry)
        evidence_report = agent_api.validate_workflow_evidence(
            workflow_request,
            registry,
            require_structured=args.require_structured_evidence,
        )
        if not evidence_report["valid"]:
            print_json({"evidence_validation": evidence_report})
            return 1
    result = agent_api.check_workflow(
        adapter=args.adapter,
        request=args.request,
        candidate=args.candidate,
        evidence=evidence,
        constraints=constraints,
        workflow_id=args.workflow_id,
        gallery_path=args.gallery,
    )
    result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    if args.shadow_mode:
        result = agent_api.apply_shadow_mode(result)
    if args.audit_log:
        record = agent_api.audit_workflow_check(workflow_request, result)
        agent_api.append_audit_record(args.audit_log, record)
    print_json(result)
    return 0 if args.shadow_mode or result["gate_decision"] == "pass" else 1


def command_workflow_batch(args):
    started_at = time.perf_counter()
    batch_request = agent_api.load_json_file(args.batch)
    if args.evidence_registry:
        registry = agent_api.load_evidence_registry(args.evidence_registry)
        evidence_report = agent_api.validate_workflow_batch_evidence(
            batch_request,
            registry,
            require_structured=args.require_structured_evidence,
        )
        if not evidence_report["valid"]:
            print_json({"evidence_validation": evidence_report})
            return 1
    result = agent_api.check_workflow_batch(batch_request, gallery_path=args.gallery)
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    for item in result.get("results", []) if isinstance(result, dict) else []:
        if isinstance(item, dict):
            item.setdefault("audit_metadata", {})["latency_ms"] = latency_ms
    if args.shadow_mode:
        result = agent_api.apply_shadow_mode(result)
    if args.audit_log:
        record = agent_api.audit_workflow_batch(batch_request, result)
        for item in record["records"]:
            agent_api.append_audit_record(args.audit_log, item)
    print_json(result)
    return 0 if args.shadow_mode or result["summary"]["failed"] == 0 else 1


def command_validate_workflow(args):
    workflow_request = agent_api.load_json_file(args.workflow)
    report = agent_api.validate_workflow_request(workflow_request)
    if args.json:
        print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Workflow request is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_validate_workflow_batch(args):
    batch_request = agent_api.load_json_file(args.batch)
    report = agent_api.validate_workflow_batch_request(batch_request)
    if args.json:
        print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Workflow batch request is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_validate_evidence_registry(args):
    registry = agent_api.load_evidence_registry(args.evidence_registry)
    report = agent_api.validate_evidence_registry(registry)
    if args.json:
        print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Evidence registry is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_evidence_integrations(args):
    registry = agent_api.load_evidence_registry(args.evidence_registry) if args.evidence_registry else None
    report = evidence_integrations.integration_coverage_report(registry=registry)
    if args.mock_fixtures:
        fixtures = evidence_integrations.load_mock_connector_fixtures(args.mock_fixtures)
        report["mock_connectors"] = evidence_integrations.mock_connector_matrix(
            fixtures=fixtures,
            now="2026-05-05T01:00:00Z",
        )
        report["valid"] = report["valid"] and report["mock_connectors"]["valid"]
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1

    status = "valid" if report["valid"] else "missing registry coverage"
    print(f"AANA evidence connector contracts: {status} ({report['integration_count']} integration(s)).")
    if not report["registry_checked"]:
        print("- Registry coverage was not checked. Pass --evidence-registry to verify required source IDs.")
    for item in report["integrations"]:
        source_ids = ", ".join(item["required_source_ids"])
        adapters = ", ".join(item["adapter_ids"])
        coverage = "covered" if item["registry_covered"] else "not checked" if not report["registry_checked"] else "missing"
        print(f"- {item['integration_id']}: {item['title']} [{coverage}]")
        print(f"  Adapters: {adapters}")
        print(f"  Required sources: {source_ids}")
        if item["missing_source_ids"]:
            print(f"  Missing sources: {', '.join(item['missing_source_ids'])}")
    if report.get("mock_connectors"):
        mock_status = "valid" if report["mock_connectors"]["valid"] else "invalid"
        print(f"- Mock connector fixtures: {mock_status} ({report['mock_connectors']['connector_count']} connector(s)).")
        for item in report["mock_connectors"]["reports"]:
            if item["failures"]:
                codes = ", ".join(sorted({failure["code"] for failure in item["failures"]}))
                print(f"  - {item['integration_id']}: {codes}")
    return 0 if report["valid"] else 1


def command_connector_marketplace(args):
    marketplace = evidence_integrations.connector_marketplace()
    if args.json:
        print_json(marketplace)
        return 0
    print(f"AANA connector marketplace: {marketplace['connector_count']} connector contract(s).")
    print("- Families: " + ", ".join(marketplace["families"]))
    for connector in marketplace["connectors"]:
        families = ", ".join(connector["families"])
        print(f"- {connector['connector_id']}: {connector['title']} ({families})")
    return 0


def command_validate_workflow_evidence(args):
    workflow_request = agent_api.load_json_file(args.workflow)
    registry = agent_api.load_evidence_registry(args.evidence_registry)
    report = agent_api.validate_workflow_evidence(
        workflow_request,
        registry,
        require_structured=args.require_structured,
    )
    if args.json:
        print_json(report)
    else:
        status = "ready for production-readiness review" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
        print(f"Workflow evidence is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_workflow_schema(args):
    catalog = agent_api.schema_catalog()
    if args.name == "all":
        print_json(catalog)
    else:
        print_json(catalog[args.name])
    return 0


def command_validate_event(args):
    event = agent_api.load_json_file(args.event)
    registry = agent_api.load_evidence_registry(args.evidence_registry) if args.evidence_registry else None
    report = agent_api.validate_event(
        event,
        evidence_registry=registry,
        require_structured_evidence=args.require_structured_evidence,
    )
    if args.json:
        print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Agent event is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_agent_schema(args):
    catalog = agent_api.schema_catalog()
    if args.name == "all":
        print_json(catalog)
    else:
        print_json(catalog[args.name])
    return 0


def command_run_agent_examples(args):
    report = agent_api.run_agent_event_examples(events_dir=args.events_dir, gallery_path=args.gallery)
    if args.json:
        print_json(report)
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


def command_scaffold_agent_event(args):
    if args.dry_run:
        event = agent_api.build_agent_event_from_gallery(args.adapter_id, gallery_path=args.gallery, agent=args.agent)
        path = pathlib.Path(args.output_dir) / f"{args.adapter_id}.json"
        print_json(
            {
                "dry_run": True,
                "would_create": {"event": str(path)},
                "event_preview": event,
                "next_steps": [
                    f"python scripts/aana_cli.py scaffold-agent-event {args.adapter_id} --output-dir {args.output_dir}",
                    f"python scripts/aana_cli.py validate-event --event {path}",
                    f"python scripts/aana_cli.py agent-check --event {path}",
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
    print_json({"created": created})
    return 0


def command_policy_presets(args):
    presets = agent_api.list_policy_presets()
    if args.json:
        print_json({"policy_presets": presets})
        return 0
    print("AANA agent policy presets:")
    for name, preset in presets.items():
        adapters = ", ".join(preset["recommended_adapters"]) or "custom adapter needed"
        print(f"- {name}: {preset['description']}")
        print(f"  Recommended adapters: {adapters}")
    return 0


def command_audit_validate(args):
    records = agent_api.load_audit_records(args.audit_log)
    report = agent_api.validate_audit_records(records)
    redaction = agent_api.audit_redaction_report(records)
    report = {
        "valid": report["valid"] and redaction["valid"],
        "record_count": report["record_count"],
        "schema": report,
        "redaction": redaction,
    }
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "valid" if report["valid"] else "invalid"
    print(f"AANA audit validation: {status} ({report['record_count']} record(s)).")
    for issue in report["schema"]["issues"] + report["redaction"]["issues"]:
        print(f"- {issue['level']} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_audit_summary(args):
    summary = agent_api.summarize_audit_file(args.audit_log)
    if args.json:
        print_json(summary)
        return 0
    print(f"AANA audit summary: {summary['total']} record(s).")
    print("Gate decisions:")
    for key, value in sorted(summary["gate_decisions"].items()):
        print(f"- {key}: {value}")
    print("Recommended actions:")
    for key, value in sorted(summary["recommended_actions"].items()):
        print(f"- {key}: {value}")
    print("Decision cases:")
    for key, value in sorted(summary.get("decision_cases", {}).items()):
        print(f"- {key}: {value}")
    print("Top violation codes:")
    for key, value in list(summary["violation_codes"].items())[:10]:
        print(f"- {key}: {value}")
    return 0


def command_audit_metrics(args):
    metrics = agent_api.export_audit_metrics_file(args.audit_log, output_path=args.output)
    if args.json:
        print_json(metrics)
        return 0
    print(f"AANA audit metrics export: {metrics['record_count']} record(s).")
    if args.output:
        print(f"- Metrics file: {args.output}")
    print("Core metrics:")
    for key in [
        "audit_records_total",
        "gate_decision_count",
        "recommended_action_count",
        "violation_code_count",
        "adapter_check_count",
        "shadow_records_total",
        "shadow_would_action_count",
        "shadow_would_pass_count",
        "shadow_would_revise_count",
        "shadow_would_defer_count",
        "shadow_would_refuse_count",
        "aix_score_average",
        "aix_decision_count",
        "aix_hard_blocker_count",
    ]:
        if key in metrics["metrics"]:
            print(f"- {key}: {metrics['metrics'][key]}")
    if metrics["unavailable_metrics"]:
        print("Unavailable from audit JSONL:")
        for key in metrics["unavailable_metrics"]:
            print(f"- {key}")
    return 0


def command_audit_drift(args):
    report = agent_api.audit_aix_drift_report_file(
        args.audit_log,
        output_path=args.output,
        baseline_metrics_path=args.baseline_metrics,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "valid" if report["valid"] else "drift detected"
    print(f"AANA AIx drift report: {status} ({report['record_count']} record(s)).")
    if args.output:
        print(f"- Drift report file: {args.output}")
    print("Core AIx metrics:")
    for key in ["aix_score_average", "aix_score_min", "aix_score_max", "aix_decision_count", "aix_hard_blocker_count"]:
        if key in report["metrics"]:
            print(f"- {key}: {report['metrics'][key]}")
    if report["issues"]:
        print("Issues:")
        for issue in report["issues"]:
            print(f"- {issue['level']} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_audit_reviewer_report(args):
    report = agent_api.write_audit_reviewer_report(
        args.audit_log,
        args.output,
        metrics_path=args.metrics,
        drift_report_path=args.drift_report,
        manifest_path=args.manifest,
    )
    if args.json:
        print_json(report)
        return 0
    print("AANA audit reviewer report created.")
    print(f"- Report: {report['output_path']}")
    print(f"- Audit log: {report['audit_log_path']}")
    return 0


def command_audit_manifest(args):
    manifest = agent_api.create_audit_integrity_manifest(
        args.audit_log,
        manifest_path=args.output,
        previous_manifest_path=args.previous_manifest,
    )
    if args.json:
        print_json(manifest)
        return 0
    print("AANA audit integrity manifest created.")
    print(f"- Audit log: {manifest['audit_log_path']}")
    if args.output:
        print(f"- Manifest: {args.output}")
    print(f"- Records: {manifest['record_count']}")
    print(f"- Audit SHA-256: {manifest['audit_log_sha256']}")
    print(f"- Manifest SHA-256: {manifest['manifest_sha256']}")
    return 0


def command_audit_verify(args):
    report = agent_api.verify_audit_integrity_manifest(args.manifest)
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "PASS" if report["valid"] else "FAIL"
    print(f"AANA audit integrity verification: {status}")
    print(f"- Manifest: {report['manifest_path']}")
    print(f"- Audit log: {report['audit_log_path']}")
    print(f"- Records: {report['record_count']}")
    if report["issues"]:
        print("Issues:")
        for issue in report["issues"]:
            print(f"- {issue['level']} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_pilot_certify(args):
    report = pilot_certification.pilot_readiness_report(
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
        cli_commands=cli_command_matrix(),
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    status = "pass" if report["valid"] else "fail"
    print(
        "AANA pilot certification: "
        f"{status} - {summary['score_percent']}/100 "
        f"({summary['readiness_level']}, {summary['surfaces']} surface(s), {summary['gates']} gate(s))."
    )
    print("Readiness matrix:")
    for surface in report["surfaces"]:
        print(
            f"- {surface['surface_id']}: {surface['status']} "
            f"{surface['score_percent']}/100 "
            f"({surface['summary']['failures']} failure(s), {surface['summary']['warnings']} warning(s))"
        )
        for gate in surface["gates"]:
            print(f"  - {gate['id']}: {gate['status']} ({gate['score']}/{gate['weight']}) - {gate['message']}")
    return 0 if report["valid"] else 1


def command_certify_bundle(args):
    report = bundle_certification.certify_bundle_report(
        args.bundle_id,
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
        mock_fixtures_path=args.mock_fixtures,
        certification_policy_path=args.certification_policy,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    status = "pass" if report["valid"] else "fail"
    print(
        f"AANA bundle certification ({report['bundle_id']}): "
        f"{status} - {summary['score_percent']}/100 "
        f"({summary['readiness_level']}, {summary['surfaces']} surface(s), {summary['failures']} failure(s))."
    )
    print("Required bundle declarations:")
    print(f"- core_adapter_ids: {len(report['manifest']['core_adapter_ids'])}")
    print(f"- required_evidence_connectors: {len(report['manifest']['required_evidence_connectors'])}")
    print(f"- human_review_required_for: {len(report['manifest']['human_review_required_for'])}")
    print(f"- minimum_validation: {'present' if report['manifest']['minimum_validation'] else 'missing'}")
    for surface in report["surfaces"]:
        print(f"- {surface['surface_id']}: {surface['status']} {surface['score_percent']}/100")
        for check in surface.get("checks", []):
            print(f"  - {check['id']}: {check['status']} - {check['message']}")
    return 0 if report["valid"] else 1


def command_enterprise_certify(args):
    report = enterprise_family.enterprise_certification_report(
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
        mock_fixtures_path=args.mock_fixtures,
        certification_policy_path=args.certification_policy,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    status = "pass" if report["valid"] else "fail"
    print(
        "AANA enterprise certification: "
        f"{status} - {summary['score_percent']}/100 "
        f"({summary['readiness_level']}, {summary['surfaces']} surface(s), {summary['failures']} failure(s))."
    )
    for surface in report["surfaces"]:
        print(f"- {surface['surface_id']}: {surface['status']} {surface['score_percent']}/100")
        for check in surface["checks"]:
            print(f"  - {check['id']}: {check['status']} ({check['score']}/{check['weight']}) - {check['message']}")
    return 0 if report["valid"] else 1


def command_personal_certify(args):
    report = personal_family.personal_certification_report(
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
        mock_fixtures_path=args.mock_fixtures,
        certification_policy_path=args.certification_policy,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    status = "pass" if report["valid"] else "fail"
    print(
        "AANA personal productivity certification: "
        f"{status} - {summary['score_percent']}/100 "
        f"({summary['readiness_level']}, {summary['surfaces']} surface(s), {summary['failures']} failure(s))."
    )
    for surface in report["surfaces"]:
        print(f"- {surface['surface_id']}: {surface['status']} {surface['score_percent']}/100")
        for check in surface["checks"]:
            print(f"  - {check['id']}: {check['status']} ({check['score']}/{check['weight']}) - {check['message']}")
    return 0 if report["valid"] else 1


def command_civic_certify(args):
    report = civic_family.civic_certification_report(
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
        mock_fixtures_path=args.mock_fixtures,
        certification_policy_path=args.certification_policy,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    status = "pass" if report["valid"] else "fail"
    print(
        "AANA government/civic certification: "
        f"{status} - {summary['score_percent']}/100 "
        f"({summary['readiness_level']}, {summary['surfaces']} surface(s), {summary['failures']} failure(s))."
    )
    for surface in report["surfaces"]:
        print(f"- {surface['surface_id']}: {surface['status']} {surface['score_percent']}/100")
        for check in surface["checks"]:
            print(f"  - {check['id']}: {check['status']} ({check['score']}/{check['weight']}) - {check['message']}")
    return 0 if report["valid"] else 1


def command_production_certify(args):
    report = production_certification.production_certification_report_from_paths(
        certification_policy_path=args.certification_policy,
        deployment_manifest_path=args.deployment_manifest,
        governance_policy_path=args.governance_policy,
        evidence_registry_path=args.evidence_registry,
        observability_policy_path=args.observability_policy,
        audit_log_path=args.audit_log,
        external_evidence_path=args.external_evidence,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    print(
        "AANA production certification: "
        f"{summary['status']} ({summary['readiness_level']}, "
        f"{summary['failures']} failure(s), {summary['warnings']} warning(s), {summary['checks']} check(s))."
    )
    print(report["production_positioning"])
    print(report["certification_scope"])
    print(f"Repo-local readiness: {'ready' if report['repo_local_ready'] else 'not ready'}")
    print(f"Deployment readiness: {'ready' if report['deployment_ready'] else 'not ready'}")
    if not report["production_certified"]:
        print("Production certified: no; final certification remains an external owner/governance decision.")
    print("Readiness boundary:")
    for level, details in report["readiness_boundary"].items():
        print(f"- {level}: {details['certification_line']}")
    print("Certification checks:")
    for check in report["checks"]:
        print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
        for issue in check.get("details", {}).get("issues", []):
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
        for issue in check.get("details", {}).get("metrics", {}).get("issues", []):
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_readiness_matrix(args):
    matrix = production_certification.certification_program_matrix()
    if args.json:
        print_json(matrix)
        return 0
    print("AANA public readiness matrix")
    print(matrix["production_positioning"])
    for level, details in matrix["levels"].items():
        print(f"- {level}: {', '.join(details['required_gates'])}")
    for family, details in matrix["families"].items():
        print(f"- {family}: {', '.join(details['required_gates'])}")
    return 0


def production_preflight_report(
    gallery_path=DEFAULT_GALLERY,
    deployment_manifest=None,
    evidence_registry=None,
    observability_policy=None,
):
    checks = []
    checks.append(
        check_status(
            "bridge_auth_boundary",
            "pass" if os.environ.get("AANA_BRIDGE_TOKEN") else "warn",
            "AANA_BRIDGE_TOKEN is configured." if os.environ.get("AANA_BRIDGE_TOKEN") else "AANA_BRIDGE_TOKEN is not set; POST auth will be optional unless --auth-token is passed.",
        )
    )
    checks.append(
        check_status(
            "redacted_audit_records",
            "pass",
            "Redacted audit helpers and JSONL summary support are available.",
            {
                "helpers": [
                    "audit_event_check",
                    "audit_workflow_check",
                    "audit_workflow_batch",
                    "append_audit_record",
                    "summarize_audit_file",
                    "create_audit_integrity_manifest",
                    "verify_audit_integrity_manifest",
                ]
            },
        )
    )
    checks.append(
        check_status(
            "structured_evidence_contract",
            "pass",
            "Workflow Contract accepts structured evidence objects with source_id, retrieved_at, trust_tier, redaction_status, and text.",
        )
    )
    if evidence_registry:
        try:
            registry = agent_api.load_evidence_registry(evidence_registry)
            report = agent_api.validate_evidence_registry(registry)
            checks.append(
                check_status(
                    "evidence_registry",
                    "pass" if report["production_ready"] else "fail" if not report["valid"] else "warn",
                    "Evidence registry satisfies production-readiness checks."
                    if report["production_ready"]
                    else "Evidence registry has issues.",
                    report,
                )
            )
            integrations = evidence_integrations.integration_coverage_report(registry=registry)
            checks.append(
                check_status(
                    "evidence_integrations",
                    "pass" if integrations["valid"] else "fail",
                    "Evidence registry covers production integration stubs."
                    if integrations["valid"]
                    else "Evidence registry is missing sources required by production integration stubs.",
                    integrations,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("evidence_registry", "fail", str(exc)))
    if observability_policy:
        try:
            policy = agent_api.load_json_file(observability_policy)
            report = production.validate_observability_policy(policy)
            checks.append(
                check_status(
                    "observability_policy",
                    "pass" if report["production_ready"] else "fail" if not report["valid"] else "warn",
                    "Observability policy satisfies production-readiness checks."
                    if report["production_ready"]
                    else "Observability policy has issues.",
                    report,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("observability_policy", "fail", str(exc)))

    try:
        gallery = load_gallery(gallery_path)
        adapter_reports = []
        missing_metadata = []
        malformed_metadata = []
        for entry in gallery_entries(gallery):
            adapter_path = ROOT / entry["adapter_path"]
            adapter = validate_adapter.load_adapter(adapter_path)
            report = validate_adapter.validate_adapter(adapter)
            adapter_reports.append(
                {
                    "id": entry.get("id"),
                    "valid": report["valid"],
                    "errors": report["errors"],
                    "warnings": report["warnings"],
                }
            )
            if not report["valid"]:
                malformed_metadata.append(entry.get("id"))
            if any(issue["path"].startswith("production_readiness") for issue in report["issues"]):
                missing_metadata.append(entry.get("id"))
        status = "pass"
        message = "Gallery adapters validate with production-readiness metadata."
        if malformed_metadata:
            status = "fail"
            message = "One or more gallery adapters fail validation."
        elif missing_metadata:
            status = "warn"
            message = "One or more gallery adapters are missing production-readiness metadata."
        checks.append(
            check_status(
                "adapter_production_metadata",
                status,
                message,
                {"adapters": adapter_reports, "needs_metadata": missing_metadata},
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(check_status("adapter_production_metadata", "fail", str(exc)))

    if deployment_manifest:
        try:
            manifest = agent_api.load_json_file(deployment_manifest)
            report = production.validate_deployment_manifest(manifest)
            checks.append(
                check_status(
                    "deployment_manifest",
                    "pass" if report["production_ready"] else "fail" if not report["valid"] else "warn",
                    "Deployment manifest satisfies production-readiness checks."
                    if report["production_ready"]
                    else "Deployment manifest has issues that must be resolved before launch.",
                    report,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("deployment_manifest", "fail", str(exc)))
    else:
        external_gates = [
            "TLS termination and authenticated network clients",
            "Rate limits and deployment-level request controls",
            "Immutable audit sink and retention policy",
            "Evidence-source authorization and freshness checks",
            "Dashboards or alerts for gate/action/violation/AIx drift",
            "Domain-owner signoff for production adapters",
            "Human-review queue for high-impact or low-confidence decisions",
        ]
        checks.append(
            check_status(
                "external_deployment_gates",
                "warn",
                "Pass --deployment-manifest to validate selected infrastructure and operating gates.",
                {"remaining": external_gates},
            )
        )

    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    return {
        "valid": not failed,
        "production_ready": not failed and not warnings,
        "summary": {
            "status": "pass" if not failed and not warnings else "warn" if not failed else "fail",
            "checks": len(checks),
            "failures": len(failed),
            "warnings": len(warnings),
        },
        "checks": checks,
    }


def command_production_preflight(args):
    report = production_preflight_report(
        gallery_path=args.gallery,
        deployment_manifest=args.deployment_manifest,
        evidence_registry=args.evidence_registry,
        observability_policy=args.observability_policy,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    print(
        f"AANA production preflight: {summary['status']} "
        f"({summary['failures']} failure(s), {summary['warnings']} warning(s))."
    )
    for check in report["checks"]:
        print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
        remaining = check.get("details", {}).get("remaining", [])
        for item in remaining:
            print(f"  - {item}")
        for issue in check.get("details", {}).get("issues", []):
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_validate_deployment(args):
    manifest = agent_api.load_json_file(args.deployment_manifest)
    report = production.validate_deployment_manifest(manifest)
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "ready for production-readiness review" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
    print(f"Deployment manifest is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
    for issue in report["issues"]:
        print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_validate_governance(args):
    policy = agent_api.load_json_file(args.governance_policy)
    report = production.validate_governance_policy(policy)
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "ready for production-readiness review" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
    print(f"Governance policy is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
    for issue in report["issues"]:
        print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def command_validate_observability(args):
    policy = agent_api.load_json_file(args.observability_policy)
    report = production.validate_observability_policy(policy)
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    status = "ready for production-readiness review" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
    print(f"Observability policy is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
    for issue in report["issues"]:
        print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def release_check_report(
    gallery_path=DEFAULT_GALLERY,
    deployment_manifest=None,
    governance_policy=None,
    evidence_registry=None,
    observability_policy=None,
    audit_log=None,
    min_aix_score_average=0.85,
    min_aix_score_min=0.5,
    max_aix_hard_blockers=0,
    allowed_aix_decisions=None,
    run_local_check=True,
):
    checks = []
    if run_local_check:
        completed = subprocess.run(
            [sys.executable, "scripts/dev.py", "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        checks.append(
            check_status(
                "local_check_suite",
                "pass" if completed.returncode == 0 else "fail",
                "scripts/dev.py check passed." if completed.returncode == 0 else "scripts/dev.py check failed.",
                {"returncode": completed.returncode},
            )
        )
    else:
        checks.append(check_status("local_check_suite", "warn", "Skipped by --skip-local-check."))

    doctor = doctor_report(gallery_path=gallery_path)
    checks.append(
        check_status(
            "doctor",
            "pass" if doctor["valid"] else "fail",
            "Doctor checks pass." if doctor["valid"] else "Doctor checks failed.",
            doctor["summary"],
        )
    )

    freeze = contract_freeze.contract_freeze_report(
        gallery_path=gallery_path,
        evidence_registry_path=evidence_registry,
    )
    checks.append(
        check_status(
            "contract_freeze",
            "pass" if freeze["valid"] else "fail",
            "Public contracts are frozen and compatibility fixtures pass."
            if freeze["valid"]
            else "Public contract freeze checks failed.",
            freeze["summary"],
        )
    )

    try:
        tuning = adapter_aix_tuning_report(load_gallery(gallery_path))
        checks.append(
            check_status(
                "adapter_aix_tuning",
                "pass" if tuning["valid"] else "fail",
                "Adapter AIx tuning meets declared risk tiers."
                if tuning["valid"]
                else "Adapter AIx tuning is missing or below declared risk-tier requirements.",
                {
                    "adapter_count": tuning["adapter_count"],
                    "failing_count": tuning["failing_count"],
                    "risk_tier_counts": tuning["risk_tier_counts"],
                    "issues": tuning["issues"],
                },
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(check_status("adapter_aix_tuning", "fail", str(exc), {"gallery": str(gallery_path)}))

    try:
        gallery_report = validate_adapter_gallery.validate_gallery(
            load_gallery(gallery_path),
            run_examples=True,
        )
        completeness = gallery_report.get("catalog_completeness", {})
        checks.append(
            check_status(
                "adapter_catalog",
                "pass" if gallery_report["valid"] else "fail",
                "Adapter catalog metadata, examples, AIx, evidence, docs links, and completeness gate passed."
                if gallery_report["valid"]
                else "Adapter catalog validation failed and blocks release.",
                {
                    "errors": gallery_report["errors"],
                    "warnings": gallery_report["warnings"],
                    "checked_examples": len(gallery_report.get("checked_examples", [])),
                    "catalog_completeness": completeness,
                    "issues": gallery_report["issues"],
                },
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(check_status("adapter_catalog", "fail", str(exc), {"gallery": str(gallery_path)}))

    preflight = production_preflight_report(
        gallery_path=gallery_path,
        deployment_manifest=deployment_manifest,
        evidence_registry=evidence_registry,
        observability_policy=observability_policy,
    )
    checks.append(
        check_status(
            "production_preflight",
            "pass" if preflight["production_ready"] else "fail" if not preflight["valid"] else "warn",
            "Production preflight checks pass; external production certification still requires live evidence connectors, domain owner signoff, audit retention, observability, and human review paths."
            if preflight["production_ready"]
            else "Production preflight has warnings or failures.",
            preflight["summary"],
        )
    )

    if governance_policy:
        try:
            policy = agent_api.load_json_file(governance_policy)
            governance = production.validate_governance_policy(policy)
            checks.append(
                check_status(
                    "governance_policy",
                    "pass" if governance["production_ready"] else "fail" if not governance["valid"] else "warn",
                    "Governance policy satisfies production-readiness checks."
                    if governance["production_ready"]
                    else "Governance policy has issues.",
                    governance,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("governance_policy", "fail", str(exc)))
    else:
        checks.append(check_status("governance_policy", "warn", "Pass --governance-policy to validate human governance gates."))

    if observability_policy:
        try:
            policy = agent_api.load_json_file(observability_policy)
            observability = production.validate_observability_policy(policy)
            checks.append(
                check_status(
                    "observability_policy",
                    "pass" if observability["production_ready"] else "fail" if not observability["valid"] else "warn",
                    "Observability policy satisfies production-readiness checks."
                    if observability["production_ready"]
                    else "Observability policy has issues.",
                    observability,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("observability_policy", "fail", str(exc)))
    else:
        checks.append(check_status("observability_policy", "warn", "Pass --observability-policy to validate dashboard, alert, and drift-review gates."))

    if audit_log:
        try:
            metrics = agent_api.export_audit_metrics_file(audit_log)
            aix_release = production.validate_aix_audit_metrics(
                metrics,
                min_average_score=min_aix_score_average,
                min_min_score=min_aix_score_min,
                max_hard_blockers=max_aix_hard_blockers,
                allowed_decisions=allowed_aix_decisions,
            )
            checks.append(
                check_status(
                    "aix_audit_enforcement",
                    "pass" if aix_release["production_ready"] else "fail" if not aix_release["valid"] else "warn",
                    "Audit AIx release gates passed." if aix_release["production_ready"] else "Audit AIx release gates failed.",
                    {"audit_log": str(audit_log), "metrics": metrics, "aix_release": aix_release},
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("aix_audit_enforcement", "fail", str(exc), {"audit_log": str(audit_log)}))
    else:
        checks.append(
            check_status(
                "aix_audit_enforcement",
                "warn",
                "Pass --audit-log to enforce AIx score, hard-blocker, and decision-drift release gates.",
            )
        )

    required_files = [
        "CHANGELOG.md",
        "docs/production-readiness-plan.md",
        "docs/aana-workflow-contract.md",
        "docs/agent-integration.md",
    ]
    missing = [path for path in required_files if not (ROOT / path).exists()]
    checks.append(
        check_status(
            "release_documentation",
            "pass" if not missing else "fail",
            "Release and production-readiness docs are present." if not missing else "Required release docs are missing.",
            {"missing": missing},
        )
    )

    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    return {
        "valid": not failed,
        "release_ready": not failed and not warnings,
        "summary": {
            "status": "pass" if not failed and not warnings else "warn" if not failed else "fail",
            "checks": len(checks),
            "failures": len(failed),
            "warnings": len(warnings),
        },
        "checks": checks,
    }


def command_release_check(args):
    report = release_check_report(
        gallery_path=args.gallery,
        deployment_manifest=args.deployment_manifest,
        governance_policy=args.governance_policy,
        evidence_registry=args.evidence_registry,
        observability_policy=args.observability_policy,
        audit_log=args.audit_log,
        min_aix_score_average=args.min_aix_score_average,
        min_aix_score_min=args.min_aix_score_min,
        max_aix_hard_blockers=args.max_aix_hard_blockers,
        allowed_aix_decisions=args.allowed_aix_decision,
        run_local_check=not args.skip_local_check,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    print(f"AANA release check: {summary['status']} ({summary['failures']} failure(s), {summary['warnings']} warning(s)).")
    for check in report["checks"]:
        print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
        for issue in check.get("details", {}).get("issues", []):
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
        completeness = check.get("details", {}).get("catalog_completeness")
        if completeness:
            print(
                f"  - Catalog completeness: {completeness.get('score')} "
                f"(weak entries: {completeness.get('weak_entry_count')})"
            )
    return 0 if report["valid"] else 1


def command_contract_freeze(args):
    report = contract_freeze.contract_freeze_report(
        gallery_path=args.gallery,
        evidence_registry_path=args.evidence_registry,
    )
    if args.json:
        print_json(report)
        return 0 if report["valid"] else 1
    summary = report["summary"]
    print(
        f"AANA contract freeze: {summary['status']} "
        f"({summary['failures']} failure(s), {summary['contracts']} contract(s), {summary['schemas']} schema(s))."
    )
    for check in report["checks"]:
        print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
        for issue in check.get("details", {}).get("issues", []):
            print(f"  - {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


def check_status(name, status, message, details=None):
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def has_real_secret(*names):
    placeholders = {"", "your_openai_api_key_here", "your_anthropic_api_key_here", "your_provider_key_here"}
    for name in names:
        value = os.environ.get(name, "").strip()
        if value and value not in placeholders:
            return True
    return False


def provider_status():
    common.load_dotenv()
    provider = common.model_provider()
    if provider == "openai":
        ready = has_real_secret("AANA_API_KEY", "OPENAI_API_KEY")
        endpoint = os.environ.get("AANA_RESPONSES_URL") or os.environ.get("OPENAI_RESPONSES_URL")
        base_url = os.environ.get("AANA_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        return check_status(
            "provider_config",
            "pass" if ready else "warn",
            "OpenAI-compatible provider is configured." if ready else "No live OpenAI-compatible API key found. Local demos still work.",
            {
                "provider": provider,
                "api_key_present": ready,
                "custom_endpoint_configured": bool(endpoint or base_url),
            },
        )
    if provider == "anthropic":
        ready = has_real_secret("ANTHROPIC_API_KEY", "AANA_API_KEY")
        return check_status(
            "provider_config",
            "pass" if ready else "warn",
            "Anthropic provider is configured." if ready else "No live Anthropic API key found. Local demos still work.",
            {
                "provider": provider,
                "api_key_present": ready,
                "custom_endpoint_configured": bool(os.environ.get("ANTHROPIC_MESSAGES_URL") or os.environ.get("ANTHROPIC_BASE_URL")),
            },
        )
    return check_status(
        "provider_config",
        "fail",
        f"Unsupported AANA_PROVIDER {provider!r}. Supported providers: openai, anthropic.",
        {"provider": provider},
    )


def doctor_report(gallery_path=DEFAULT_GALLERY):
    checks = []
    python_ok = sys.version_info >= (3, 10)
    checks.append(
        check_status(
            "python",
            "pass" if python_ok else "fail",
            f"Python {platform.python_version()} detected.",
            {"executable": sys.executable, "requires": ">=3.10"},
        )
    )

    checks.append(
        check_status(
            "command_hub",
            "pass",
            "AANA command hub is importable.",
            {"root": str(ROOT), "script": str(pathlib.Path(__file__).resolve())},
        )
    )

    try:
        gallery = load_gallery(gallery_path)
        gallery_report = validate_adapter_gallery.validate_gallery(gallery, run_examples=True)
        checks.append(
            check_status(
                "adapter_gallery",
                "pass" if gallery_report["valid"] else "fail",
                f"Adapter gallery checked with {len(gallery_report.get('checked_examples', []))} executable examples.",
                {
                    "errors": gallery_report["errors"],
                    "warnings": gallery_report["warnings"],
                    "checked_examples": gallery_report.get("checked_examples", []),
                },
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(check_status("adapter_gallery", "fail", str(exc)))

    try:
        agent_examples = agent_api.run_agent_event_examples(gallery_path=gallery_path)
        checks.append(
            check_status(
                "agent_event_examples",
                "pass" if agent_examples["valid"] else "fail",
                f"{agent_examples['count']} agent event examples checked.",
                {"checked_examples": agent_examples["checked_examples"]},
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(check_status("agent_event_examples", "fail", str(exc)))

    schemas = agent_api.schema_catalog()
    schema_ok = {
        "agent_event",
        "agent_check_result",
        "workflow_request",
        "workflow_batch_request",
        "workflow_result",
        "workflow_batch_result",
    }.issubset(schemas)
    checks.append(
        check_status(
            "agent_schemas",
            "pass" if schema_ok else "fail",
            "Agent and workflow schemas are available." if schema_ok else "Agent or workflow schemas are incomplete.",
            {"schemas": sorted(schemas.keys())},
        )
    )

    checks.append(provider_status())
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


def command_doctor(args):
    report = doctor_report(gallery_path=args.gallery)
    if args.json:
        print_json(report)
    else:
        summary = report["summary"]
        print(f"AANA doctor: {summary['status']} ({summary['failures']} failure(s), {summary['warnings']} warning(s)).")
        for check in report["checks"]:
            print(f"- {check['status'].upper()} {check['name']}: {check['message']}")
    return 0 if report["valid"] else 1


def command_validate_adapter(args):
    adapter = validate_adapter.load_adapter(args.adapter)
    report = validate_adapter.validate_adapter(adapter)
    print_json(report) if args.json else print_validate_report(report)
    return 0 if report["valid"] else 1


def print_validate_report(report):
    status = "valid" if report["valid"] else "invalid"
    print(f"Adapter is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
    for issue in report["issues"]:
        print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    print("Next steps:")
    for step in report.get("next_steps", []):
        print(f"- {step}")


def command_validate_gallery(args):
    gallery = load_gallery(args.gallery)
    report = validate_adapter_gallery.validate_gallery(gallery, run_examples=args.run_examples)
    if args.json:
        print_json(report)
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter gallery is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        completeness = report.get("catalog_completeness", {})
        if completeness:
            print(
                f"Catalog completeness: {completeness.get('score')} "
                f"(weak entries: {completeness.get('weak_entry_count')})"
            )
        for item in report["checked_examples"]:
            print(
                f"- {item['id']}: gate={item['gate_decision']} "
                f"action={item['recommended_action']} aix={item.get('aix_decision')}"
            )
    return 0 if report["valid"] else 1


def command_scaffold(args):
    if args.dry_run:
        output_dir = pathlib.Path(args.output_dir)
        slug = new_adapter.slugify(args.domain)
        would_create = {
            "adapter": str(output_dir / f"{slug}_adapter.json"),
            "prompt": str(output_dir / f"{slug}_adapter_prompt.txt"),
            "bad_candidate": str(output_dir / f"{slug}_adapter_bad_candidate.txt"),
            "readme": str(output_dir / f"{slug}_adapter_README.md"),
        }
        print_json(
            {
                "dry_run": True,
                "would_create": would_create,
                "next_steps": [
                    f"python scripts/aana_cli.py scaffold \"{args.domain}\" --output-dir {args.output_dir}",
                    f"python scripts/aana_cli.py validate-adapter {would_create['adapter']}",
                    "Replace the starter prompt and bad candidate with a real workflow case.",
                ],
            }
        )
        return 0

    created = new_adapter.scaffold(args.domain, args.output_dir, force=args.force)
    print_json(
        {
            "created": created,
            "next_steps": [
                f"python scripts/aana_cli.py validate-adapter {created['adapter']}",
                "Replace the starter prompt and bad candidate with a real workflow case.",
                "Add the adapter to examples/adapter_gallery.json when it has an executable verifier path.",
            ],
        }
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="AANA platform command hub.")
    parser.add_argument("--gallery", default=str(DEFAULT_GALLERY), help="Path to adapter gallery JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cli_contract_parser = subparsers.add_parser("cli-contract", help="Print the stable CLI command, exit-code, and error contract.")
    cli_contract_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    cli_contract_parser.set_defaults(func=command_cli_contract)

    list_parser = subparsers.add_parser("list", help="List gallery adapters.")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    list_parser.set_defaults(func=command_list)

    aix_tuning_parser = subparsers.add_parser("aix-tuning", help="Report adapter AIx risk tiers and tuning thresholds.")
    aix_tuning_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    aix_tuning_parser.set_defaults(func=command_aix_tuning)

    support_aix_parser = subparsers.add_parser("support-aix-calibration", help="Run support-specific AIx calibration cases.")
    support_aix_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    support_aix_parser.add_argument(
        "--support-fixtures",
        default=str(ROOT / "examples" / "support_workflow_contract_examples.json"),
        help="Path to canonical support workflow fixtures.",
    )
    support_aix_parser.add_argument(
        "--calibration-fixtures",
        default=str(ROOT / "examples" / "support_aix_calibration_cases.json"),
        help="Path to support AIx calibration fixture labels.",
    )
    support_aix_parser.set_defaults(func=command_support_aix_calibration)

    doctor_parser = subparsers.add_parser("doctor", help="Check local AANA platform readiness.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    doctor_parser.set_defaults(func=command_doctor)

    run_parser = subparsers.add_parser("run", help="Run a gallery adapter by id.")
    run_parser.add_argument("adapter_id", help="Gallery adapter id, such as travel_planning.")
    run_parser.set_defaults(func=command_run)

    run_file_parser = subparsers.add_parser("run-file", help="Run an adapter JSON file directly for adapter development diagnostics.")
    run_file_parser.add_argument("--adapter", required=True, help="Path to adapter JSON.")
    run_file_parser.add_argument("--prompt", required=True, help="Prompt to run.")
    run_file_parser.add_argument("--candidate", default=None, help="Optional candidate answer.")
    run_file_parser.add_argument("--candidate-file", default=None, help="Read candidate answer from a text file.")
    run_file_parser.set_defaults(func=command_run_file)

    agent_parser = subparsers.add_parser("agent-check", help="Check an AI-agent event against a gallery adapter.")
    agent_parser.add_argument("--event", required=True, help="Path to agent event JSON.")
    agent_parser.add_argument("--adapter-id", default=None, help="Override adapter id from the event.")
    agent_parser.add_argument("--audit-log", default=None, help="Append a redacted audit record to this JSONL file.")
    agent_parser.add_argument("--evidence-registry", default=None, help="Validate structured event evidence against this registry before checking.")
    agent_parser.add_argument("--require-structured-evidence", action="store_true", help="Reject unstructured event evidence strings before checking.")
    agent_parser.add_argument("--shadow-mode", action="store_true", help="Observe and audit what AANA would recommend without returning a blocking exit code.")
    agent_parser.set_defaults(func=command_agent_check)

    pre_tool_parser = subparsers.add_parser("pre-tool-check", help="Check an AANA pre-tool-call contract before executing a tool.")
    pre_tool_parser.add_argument("--event", required=True, help="Path to agent tool precheck JSON.")
    pre_tool_parser.add_argument("--gate-version", choices=["v1", "v2"], default="v1", help="Pre-tool-call gate version.")
    pre_tool_parser.add_argument("--validate-only", action="store_true", help="Only validate the pre-tool-call contract.")
    pre_tool_parser.add_argument("--strict-validation", action="store_true", help="Return schema validation failures before running the gate.")
    pre_tool_parser.set_defaults(func=command_pre_tool_check)

    evidence_pack_parser = subparsers.add_parser("evidence-pack", help="Summarize and validate the AANA production-candidate evidence pack.")
    evidence_pack_parser.add_argument("--manifest", default=str(DEFAULT_EVIDENCE_PACK), help="Path to production-candidate evidence-pack manifest.")
    evidence_pack_parser.add_argument("--require-existing-artifacts", action="store_true", help="Require all linked evidence artifacts to exist.")
    evidence_pack_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    evidence_pack_parser.set_defaults(func=command_evidence_pack)

    workflow_parser = subparsers.add_parser("workflow-check", help="Check a workflow request with the AANA Workflow Contract.")
    workflow_parser.add_argument("--workflow", default=None, help="Path to workflow request JSON. When provided, other workflow fields are ignored.")
    workflow_parser.add_argument("--adapter", default=None, help="Gallery adapter id, such as research_summary.")
    workflow_parser.add_argument("--request", default=None, help="User request or workflow instruction.")
    workflow_parser.add_argument("--candidate", default=None, help="Proposed output or action to check.")
    workflow_parser.add_argument("--evidence", action="append", default=[], help="Verified evidence item. Repeat as needed.")
    workflow_parser.add_argument("--constraint", action="append", default=[], help="Constraint to preserve. Repeat as needed.")
    workflow_parser.add_argument("--workflow-id", default=None, help="Optional workflow id for logs/results.")
    workflow_parser.add_argument("--audit-log", default=None, help="Append a redacted audit record to this JSONL file.")
    workflow_parser.add_argument("--evidence-registry", default=None, help="Validate workflow evidence against this registry before checking.")
    workflow_parser.add_argument("--require-structured-evidence", action="store_true", help="Reject unstructured evidence strings when validating evidence.")
    workflow_parser.add_argument("--shadow-mode", action="store_true", help="Observe and audit what AANA would recommend without returning a blocking exit code.")
    workflow_parser.set_defaults(func=command_workflow_check)

    workflow_batch_parser = subparsers.add_parser("workflow-batch", help="Check a workflow batch request JSON file.")
    workflow_batch_parser.add_argument("--batch", required=True, help="Path to workflow batch request JSON.")
    workflow_batch_parser.add_argument("--audit-log", default=None, help="Append redacted per-item audit records to this JSONL file.")
    workflow_batch_parser.add_argument("--evidence-registry", default=None, help="Validate workflow evidence against this registry before checking.")
    workflow_batch_parser.add_argument("--require-structured-evidence", action="store_true", help="Reject unstructured evidence strings when validating evidence.")
    workflow_batch_parser.add_argument("--shadow-mode", action="store_true", help="Observe and audit what AANA would recommend without returning a blocking exit code.")
    workflow_batch_parser.set_defaults(func=command_workflow_batch)

    validate_workflow_parser = subparsers.add_parser("validate-workflow", help="Validate an AANA workflow request JSON file.")
    validate_workflow_parser.add_argument("--workflow", required=True, help="Path to workflow request JSON.")
    validate_workflow_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_workflow_parser.set_defaults(func=command_validate_workflow)

    validate_workflow_batch_parser = subparsers.add_parser("validate-workflow-batch", help="Validate an AANA workflow batch request JSON file.")
    validate_workflow_batch_parser.add_argument("--batch", required=True, help="Path to workflow batch request JSON.")
    validate_workflow_batch_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_workflow_batch_parser.set_defaults(func=command_validate_workflow_batch)

    validate_evidence_registry_parser = subparsers.add_parser("validate-evidence-registry", help="Validate an AANA evidence registry JSON file.")
    validate_evidence_registry_parser.add_argument("--evidence-registry", required=True, help="Path to evidence registry JSON.")
    validate_evidence_registry_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_evidence_registry_parser.set_defaults(func=command_validate_evidence_registry)

    evidence_integrations_parser = subparsers.add_parser("evidence-integrations", help="List production evidence integration stubs and registry coverage.")
    evidence_integrations_parser.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON to check required source coverage.")
    evidence_integrations_parser.add_argument("--mock-fixtures", default=None, help="Optional mock connector fixture JSON to validate normalized evidence output.")
    evidence_integrations_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    evidence_integrations_parser.set_defaults(func=command_evidence_integrations)

    connector_marketplace_parser = subparsers.add_parser("connector-marketplace", help="List connector marketplace contract cards.")
    connector_marketplace_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    connector_marketplace_parser.set_defaults(func=command_connector_marketplace)

    validate_workflow_evidence_parser = subparsers.add_parser("validate-workflow-evidence", help="Validate workflow evidence against an evidence registry.")
    validate_workflow_evidence_parser.add_argument("--workflow", required=True, help="Path to workflow request JSON.")
    validate_workflow_evidence_parser.add_argument("--evidence-registry", required=True, help="Path to evidence registry JSON.")
    validate_workflow_evidence_parser.add_argument("--require-structured", action="store_true", help="Reject unstructured evidence strings.")
    validate_workflow_evidence_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_workflow_evidence_parser.set_defaults(func=command_validate_workflow_evidence)

    validate_event_parser = subparsers.add_parser("validate-event", help="Validate an AI-agent event contract.")
    validate_event_parser.add_argument("--event", required=True, help="Path to agent event JSON.")
    validate_event_parser.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON for source/freshness validation.")
    validate_event_parser.add_argument("--require-structured-evidence", action="store_true", help="Reject unstructured event evidence strings.")
    validate_event_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_event_parser.set_defaults(func=command_validate_event)

    schema_parser = subparsers.add_parser("agent-schema", help="Print versioned agent JSON schemas.")
    schema_parser.add_argument(
        "name",
        nargs="?",
        default="all",
        choices=["all", "agent_event", "agent_check_result"],
        help="Schema to print.",
    )
    schema_parser.set_defaults(func=command_agent_schema)

    workflow_schema_parser = subparsers.add_parser("workflow-schema", help="Print versioned workflow JSON schemas.")
    workflow_schema_parser.add_argument(
        "name",
        nargs="?",
        default="all",
        choices=["all", "workflow_request", "workflow_batch_request", "workflow_result", "workflow_batch_result"],
        help="Schema to print.",
    )
    workflow_schema_parser.set_defaults(func=command_workflow_schema)

    agent_examples_parser = subparsers.add_parser("run-agent-examples", help="Run executable agent event examples.")
    agent_examples_parser.add_argument("--events-dir", default=str(agent_api.DEFAULT_AGENT_EVENTS_DIR), help="Directory of agent event JSON files.")
    agent_examples_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    agent_examples_parser.set_defaults(func=command_run_agent_examples)

    scaffold_event_parser = subparsers.add_parser("scaffold-agent-event", help="Create a starter agent event JSON from a gallery adapter.")
    scaffold_event_parser.add_argument("adapter_id", help="Gallery adapter id, such as support_reply.")
    scaffold_event_parser.add_argument("--output-dir", default=str(agent_api.DEFAULT_AGENT_EVENTS_DIR), help="Directory for generated event JSON.")
    scaffold_event_parser.add_argument("--agent", default="openclaw", help="Agent name to place in the event.")
    scaffold_event_parser.add_argument("--force", action="store_true", help="Overwrite an existing event file.")
    scaffold_event_parser.add_argument("--dry-run", action="store_true", help="Show the event file that would be created without writing it.")
    scaffold_event_parser.set_defaults(func=command_scaffold_agent_event)

    policy_parser = subparsers.add_parser("policy-presets", help="List agent policy presets.")
    policy_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    policy_parser.set_defaults(func=command_policy_presets)

    audit_validate_parser = subparsers.add_parser("audit-validate", help="Validate redacted AANA audit JSONL records and redaction shape.")
    audit_validate_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_validate_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_validate_parser.set_defaults(func=command_audit_validate)

    audit_summary_parser = subparsers.add_parser("audit-summary", help="Summarize a redacted AANA audit JSONL file.")
    audit_summary_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_summary_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_summary_parser.set_defaults(func=command_audit_summary)

    audit_metrics_parser = subparsers.add_parser("audit-metrics", help="Export dashboard metrics from a redacted AANA audit JSONL file.")
    audit_metrics_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_metrics_parser.add_argument("--output", default=None, help="Optional path to write the metrics JSON file.")
    audit_metrics_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_metrics_parser.set_defaults(func=command_audit_metrics)

    audit_drift_parser = subparsers.add_parser("audit-drift", help="Create an AIx drift report from redacted AANA audit JSONL.")
    audit_drift_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_drift_parser.add_argument("--baseline-metrics", default=None, help="Optional previous audit metrics JSON for comparison.")
    audit_drift_parser.add_argument("--output", default=None, help="Optional path to write drift report JSON.")
    audit_drift_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_drift_parser.set_defaults(func=command_audit_drift)

    audit_reviewer_parser = subparsers.add_parser("audit-reviewer-report", help="Create a Markdown reviewer report from audit, metrics, drift, and manifest artifacts.")
    audit_reviewer_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_reviewer_parser.add_argument("--output", required=True, help="Path to write Markdown reviewer report.")
    audit_reviewer_parser.add_argument("--metrics", default=None, help="Optional audit metrics JSON path.")
    audit_reviewer_parser.add_argument("--drift-report", default=None, help="Optional AIx drift report JSON path.")
    audit_reviewer_parser.add_argument("--manifest", default=None, help="Optional audit integrity manifest JSON path.")
    audit_reviewer_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_reviewer_parser.set_defaults(func=command_audit_reviewer_report)

    audit_manifest_parser = subparsers.add_parser("audit-manifest", help="Create a SHA-256 integrity manifest for an AANA audit JSONL file.")
    audit_manifest_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_manifest_parser.add_argument("--output", required=True, help="Path to write the integrity manifest JSON file.")
    audit_manifest_parser.add_argument("--previous-manifest", default=None, help="Optional previous manifest to chain by SHA-256.")
    audit_manifest_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_manifest_parser.set_defaults(func=command_audit_manifest)

    audit_verify_parser = subparsers.add_parser("audit-verify", help="Verify an AANA audit integrity manifest.")
    audit_verify_parser.add_argument("--manifest", required=True, help="Path to audit integrity manifest JSON file.")
    audit_verify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_verify_parser.set_defaults(func=command_audit_verify)

    pilot_certify_parser = subparsers.add_parser("pilot-certify", help="Certify repo-local AANA pilot surfaces and print a public readiness score.")
    pilot_certify_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    pilot_certify_parser.add_argument("--evidence-registry", default=str(ROOT / "examples" / "evidence_registry.json"), help="Evidence registry JSON.")
    pilot_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    pilot_certify_parser.set_defaults(func=command_pilot_certify)

    bundle_certify_parser = subparsers.add_parser(
        "certify-bundle",
        help="Certify one AANA product bundle manifest, connector requirements, human-review gates, and family surfaces.",
    )
    bundle_certify_parser.add_argument(
        "bundle_id",
        choices=bundle_certification.certification_target_choices(),
        help="Bundle to certify.",
    )
    bundle_certify_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    bundle_certify_parser.add_argument(
        "--evidence-registry",
        default=str(ROOT / "examples" / "evidence_registry.json"),
        help="Evidence registry JSON.",
    )
    bundle_certify_parser.add_argument(
        "--mock-fixtures",
        default=str(ROOT / "examples" / "evidence_mock_connector_fixtures.json"),
        help="Evidence mock connector fixtures JSON.",
    )
    bundle_certify_parser.add_argument(
        "--certification-policy",
        default=None,
        help="Optional bundle certification policy JSON. Defaults to the policy for the selected bundle.",
    )
    bundle_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    bundle_certify_parser.set_defaults(func=command_certify_bundle)

    enterprise_certify_parser = subparsers.add_parser(
        "enterprise-certify",
        help="Certify the AANA Enterprise family pack, connectors, skills, surfaces, and controls.",
    )
    enterprise_certify_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    enterprise_certify_parser.add_argument(
        "--evidence-registry",
        default=str(ROOT / "examples" / "evidence_registry.json"),
        help="Evidence registry JSON.",
    )
    enterprise_certify_parser.add_argument(
        "--mock-fixtures",
        default=str(ROOT / "examples" / "evidence_mock_connector_fixtures.json"),
        help="Evidence mock connector fixtures JSON.",
    )
    enterprise_certify_parser.add_argument(
        "--certification-policy",
        default=str(ROOT / "examples" / "enterprise_certification_policy.json"),
        help="Enterprise production certification policy JSON.",
    )
    enterprise_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    enterprise_certify_parser.set_defaults(func=command_enterprise_certify)

    personal_certify_parser = subparsers.add_parser(
        "personal-certify",
        help="Certify the AANA Personal Productivity family pack, connectors, skills, local demos, and controls.",
    )
    personal_certify_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    personal_certify_parser.add_argument(
        "--evidence-registry",
        default=str(ROOT / "examples" / "evidence_registry.json"),
        help="Evidence registry JSON.",
    )
    personal_certify_parser.add_argument(
        "--mock-fixtures",
        default=str(ROOT / "examples" / "evidence_mock_connector_fixtures.json"),
        help="Evidence mock connector fixtures JSON.",
    )
    personal_certify_parser.add_argument(
        "--certification-policy",
        default=str(ROOT / "examples" / "personal_certification_policy.json"),
        help="Personal productivity certification policy JSON.",
    )
    personal_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    personal_certify_parser.set_defaults(func=command_personal_certify)

    civic_certify_parser = subparsers.add_parser(
        "civic-certify",
        help="Certify the AANA Government/Civic family pack, connectors, skills, pilot surface, and controls.",
    )
    civic_certify_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    civic_certify_parser.add_argument(
        "--evidence-registry",
        default=str(ROOT / "examples" / "evidence_registry.json"),
        help="Evidence registry JSON.",
    )
    civic_certify_parser.add_argument(
        "--mock-fixtures",
        default=str(ROOT / "examples" / "evidence_mock_connector_fixtures.json"),
        help="Evidence mock connector fixtures JSON.",
    )
    civic_certify_parser.add_argument(
        "--certification-policy",
        default=str(ROOT / "examples" / "civic_certification_policy.json"),
        help="Government/civic certification policy JSON.",
    )
    civic_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    civic_certify_parser.set_defaults(func=command_civic_certify)

    production_certify_parser = subparsers.add_parser("production-certify", help="Check the production readiness boundary from policy, audit, evidence, governance, and external deployment artifacts.")
    production_certify_parser.add_argument(
        "--certification-policy",
        default=str(ROOT / "examples" / "production_certification_template.json"),
        help="Production certification policy JSON.",
    )
    production_certify_parser.add_argument("--deployment-manifest", default=None, help="Production deployment manifest JSON.")
    production_certify_parser.add_argument("--governance-policy", default=None, help="Human-governance policy JSON.")
    production_certify_parser.add_argument("--evidence-registry", default=None, help="Evidence registry JSON.")
    production_certify_parser.add_argument("--observability-policy", default=None, help="Observability policy JSON.")
    production_certify_parser.add_argument("--audit-log", default=None, help="Redacted shadow-mode audit JSONL file.")
    production_certify_parser.add_argument("--external-evidence", default=None, help="External production evidence manifest JSON.")
    production_certify_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    production_certify_parser.set_defaults(func=command_production_certify)

    readiness_matrix_parser = subparsers.add_parser("readiness-matrix", help="Print public demo, pilot, production, and family-specific certification gates.")
    readiness_matrix_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    readiness_matrix_parser.set_defaults(func=command_readiness_matrix)

    preflight_parser = subparsers.add_parser("production-preflight", help="Check repo-local production readiness and list external gates.")
    preflight_parser.add_argument("--deployment-manifest", default=None, help="Optional deployment manifest JSON to validate external gates.")
    preflight_parser.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON to validate evidence-source gates.")
    preflight_parser.add_argument("--observability-policy", default=None, help="Optional observability policy JSON to validate dashboard, alert, and drift-review gates.")
    preflight_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    preflight_parser.set_defaults(func=command_production_preflight)

    contract_freeze_parser = subparsers.add_parser("contract-freeze", help="Validate frozen public AANA contracts and compatibility fixtures.")
    contract_freeze_parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    contract_freeze_parser.add_argument("--evidence-registry", default=None, help="Evidence registry JSON. Defaults to examples/evidence_registry.json.")
    contract_freeze_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    contract_freeze_parser.set_defaults(func=command_contract_freeze)

    deployment_parser = subparsers.add_parser("validate-deployment", help="Validate an AANA production deployment manifest.")
    deployment_parser.add_argument("--deployment-manifest", required=True, help="Path to deployment manifest JSON.")
    deployment_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    deployment_parser.set_defaults(func=command_validate_deployment)

    governance_parser = subparsers.add_parser("validate-governance", help="Validate an AANA human-governance policy JSON.")
    governance_parser.add_argument("--governance-policy", required=True, help="Path to governance policy JSON.")
    governance_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    governance_parser.set_defaults(func=command_validate_governance)

    observability_parser = subparsers.add_parser("validate-observability", help="Validate an AANA observability policy JSON.")
    observability_parser.add_argument("--observability-policy", required=True, help="Path to observability policy JSON.")
    observability_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    observability_parser.set_defaults(func=command_validate_observability)

    release_parser = subparsers.add_parser("release-check", help="Run AANA release and production-readiness gates.")
    release_parser.add_argument("--deployment-manifest", default=None, help="Optional deployment manifest JSON.")
    release_parser.add_argument("--governance-policy", default=None, help="Optional human-governance policy JSON.")
    release_parser.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON.")
    release_parser.add_argument("--observability-policy", default=None, help="Optional observability policy JSON.")
    release_parser.add_argument("--audit-log", default=None, help="Optional redacted audit JSONL file for AIx release enforcement.")
    release_parser.add_argument("--min-aix-score-average", type=float, default=0.85, help="Minimum allowed average AIx score when --audit-log is supplied.")
    release_parser.add_argument("--min-aix-score-min", type=float, default=0.5, help="Minimum allowed lowest AIx score when --audit-log is supplied.")
    release_parser.add_argument("--max-aix-hard-blockers", type=int, default=0, help="Maximum allowed AIx hard blockers when --audit-log is supplied.")
    release_parser.add_argument(
        "--allowed-aix-decision",
        action="append",
        default=None,
        help="Allowed final AIx decision in release audit logs. Can be passed multiple times; defaults to accept and revise.",
    )
    release_parser.add_argument("--skip-local-check", action="store_true", help="Skip scripts/dev.py check.")
    release_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    release_parser.set_defaults(func=command_release_check)

    validate_adapter_parser = subparsers.add_parser("validate-adapter", help="Validate one adapter JSON file.")
    validate_adapter_parser.add_argument("adapter", help="Path to adapter JSON.")
    validate_adapter_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_adapter_parser.set_defaults(func=command_validate_adapter)

    validate_gallery_parser = subparsers.add_parser("validate-gallery", help="Validate the adapter gallery.")
    validate_gallery_parser.add_argument("--run-examples", action="store_true", help="Run executable examples.")
    validate_gallery_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_gallery_parser.set_defaults(func=command_validate_gallery)

    scaffold_parser = subparsers.add_parser("scaffold", help="Create a starter adapter package.")
    scaffold_parser.add_argument("domain", help="Human-readable domain name.")
    scaffold_parser.add_argument("--output-dir", default="examples", help="Directory for generated files.")
    scaffold_parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    scaffold_parser.add_argument("--dry-run", action="store_true", help="Show files that would be created without writing them.")
    scaffold_parser.set_defaults(func=command_scaffold)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_cli_paths(args)
        return args.func(args)
    except CliError as exc:
        print_cli_error(exc, json_output=getattr(args, "json", False))
        return exc.exit_code
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error = CliError(str(exc), exit_code=EXIT_USAGE)
        print_cli_error(error, json_output=getattr(args, "json", False))
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
