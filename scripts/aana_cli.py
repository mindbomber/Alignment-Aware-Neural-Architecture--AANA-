#!/usr/bin/env python
"""Small command hub for trying and extending AANA adapters."""

import argparse
import json
import os
import pathlib
import platform
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import new_adapter
import run_adapter
import validate_adapter
import validate_adapter_gallery
from eval_pipeline import common, production
from eval_pipeline import agent_api


DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"


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


def run_entry(entry):
    adapter = run_adapter.load_adapter(ROOT / entry["adapter_path"])
    return run_adapter.run_adapter(adapter, entry["prompt"], entry.get("bad_candidate"))


def command_run(args):
    gallery = load_gallery(args.gallery)
    entry = find_entry(gallery, args.adapter_id)
    result = run_entry(entry)
    print_json(result)
    return 0 if result.get("gate_decision") == "pass" else 1


def command_run_file(args):
    adapter = run_adapter.load_adapter(args.adapter)
    candidate = args.candidate
    if args.candidate_file:
        candidate = pathlib.Path(args.candidate_file).read_text(encoding="utf-8")
    result = run_adapter.run_adapter(adapter, args.prompt, candidate)
    print_json(result)
    return 0 if result.get("gate_decision") in {"pass", "needs_adapter_implementation"} else 1


def command_agent_check(args):
    event = agent_api.load_json_file(args.event)
    response = agent_api.check_event(event, gallery_path=args.gallery, adapter_id=args.adapter_id)
    if args.audit_log:
        record = agent_api.audit_event_check(event, response)
        agent_api.append_audit_record(args.audit_log, record)
    print_json(response)
    return 0 if response["gate_decision"] == "pass" else 1


def command_workflow_check(args):
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
        if args.audit_log:
            record = agent_api.audit_workflow_check(workflow_request, result)
            agent_api.append_audit_record(args.audit_log, record)
        print_json(result)
        return 0 if result["gate_decision"] == "pass" else 1

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
    if args.audit_log:
        record = agent_api.audit_workflow_check(workflow_request, result)
        agent_api.append_audit_record(args.audit_log, record)
    print_json(result)
    return 0 if result["gate_decision"] == "pass" else 1


def command_workflow_batch(args):
    batch_request = agent_api.load_json_file(args.batch)
    if args.evidence_registry:
        registry = agent_api.load_evidence_registry(args.evidence_registry)
        reports = []
        for index, workflow_request in enumerate(batch_request.get("requests", [])):
            report = agent_api.validate_workflow_evidence(
                workflow_request,
                registry,
                require_structured=args.require_structured_evidence,
            )
            reports.append({"index": index, **report})
        if any(not report["valid"] for report in reports):
            print_json({"evidence_validation": reports})
            return 1
    result = agent_api.check_workflow_batch(batch_request, gallery_path=args.gallery)
    if args.audit_log:
        record = agent_api.audit_workflow_batch(batch_request, result)
        for item in record["records"]:
            agent_api.append_audit_record(args.audit_log, item)
    print_json(result)
    return 0 if result["summary"]["failed"] == 0 else 1


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
        status = "production-ready" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
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
    report = agent_api.validate_event(event)
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
                f"action={item['recommended_action']} expectations={expectation}"
            )
    return 0 if report["valid"] else 1


def command_scaffold_agent_event(args):
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
    print("Top violation codes:")
    for key, value in list(summary["violation_codes"].items())[:10]:
        print(f"- {key}: {value}")
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
                    "Evidence registry is production-ready."
                    if report["production_ready"]
                    else "Evidence registry has issues.",
                    report,
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
                    "Observability policy is production-ready."
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
                    "Deployment manifest is production-ready."
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
            "Dashboards or alerts for gate/action/violation drift",
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
    status = "production-ready" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
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
    status = "production-ready" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
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
    status = "production-ready" if report["production_ready"] else "valid with warnings" if report["valid"] else "invalid"
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
            "Production preflight is ready."
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
                    "Governance policy is production-ready."
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
                    "Observability policy is production-ready."
                    if observability["production_ready"]
                    else "Observability policy has issues.",
                    observability,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(check_status("observability_policy", "fail", str(exc)))
    else:
        checks.append(check_status("observability_policy", "warn", "Pass --observability-policy to validate dashboard, alert, and drift-review gates."))

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
        for item in report["checked_examples"]:
            print(f"- {item['id']}: gate={item['gate_decision']} action={item['recommended_action']}")
    return 0 if report["valid"] else 1


def command_scaffold(args):
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

    list_parser = subparsers.add_parser("list", help="List gallery adapters.")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    list_parser.set_defaults(func=command_list)

    doctor_parser = subparsers.add_parser("doctor", help="Check local AANA platform readiness.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    doctor_parser.set_defaults(func=command_doctor)

    run_parser = subparsers.add_parser("run", help="Run a gallery adapter by id.")
    run_parser.add_argument("adapter_id", help="Gallery adapter id, such as travel_planning.")
    run_parser.set_defaults(func=command_run)

    run_file_parser = subparsers.add_parser("run-file", help="Run any adapter JSON file.")
    run_file_parser.add_argument("--adapter", required=True, help="Path to adapter JSON.")
    run_file_parser.add_argument("--prompt", required=True, help="Prompt to run.")
    run_file_parser.add_argument("--candidate", default=None, help="Optional candidate answer.")
    run_file_parser.add_argument("--candidate-file", default=None, help="Read candidate answer from a text file.")
    run_file_parser.set_defaults(func=command_run_file)

    agent_parser = subparsers.add_parser("agent-check", help="Check an AI-agent event against a gallery adapter.")
    agent_parser.add_argument("--event", required=True, help="Path to agent event JSON.")
    agent_parser.add_argument("--adapter-id", default=None, help="Override adapter id from the event.")
    agent_parser.add_argument("--audit-log", default=None, help="Append a redacted audit record to this JSONL file.")
    agent_parser.set_defaults(func=command_agent_check)

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
    workflow_parser.set_defaults(func=command_workflow_check)

    workflow_batch_parser = subparsers.add_parser("workflow-batch", help="Check a workflow batch request JSON file.")
    workflow_batch_parser.add_argument("--batch", required=True, help="Path to workflow batch request JSON.")
    workflow_batch_parser.add_argument("--audit-log", default=None, help="Append redacted per-item audit records to this JSONL file.")
    workflow_batch_parser.add_argument("--evidence-registry", default=None, help="Validate workflow evidence against this registry before checking.")
    workflow_batch_parser.add_argument("--require-structured-evidence", action="store_true", help="Reject unstructured evidence strings when validating evidence.")
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

    validate_workflow_evidence_parser = subparsers.add_parser("validate-workflow-evidence", help="Validate workflow evidence against an evidence registry.")
    validate_workflow_evidence_parser.add_argument("--workflow", required=True, help="Path to workflow request JSON.")
    validate_workflow_evidence_parser.add_argument("--evidence-registry", required=True, help="Path to evidence registry JSON.")
    validate_workflow_evidence_parser.add_argument("--require-structured", action="store_true", help="Reject unstructured evidence strings.")
    validate_workflow_evidence_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_workflow_evidence_parser.set_defaults(func=command_validate_workflow_evidence)

    validate_event_parser = subparsers.add_parser("validate-event", help="Validate an AI-agent event contract.")
    validate_event_parser.add_argument("--event", required=True, help="Path to agent event JSON.")
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
    scaffold_event_parser.set_defaults(func=command_scaffold_agent_event)

    policy_parser = subparsers.add_parser("policy-presets", help="List agent policy presets.")
    policy_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    policy_parser.set_defaults(func=command_policy_presets)

    audit_summary_parser = subparsers.add_parser("audit-summary", help="Summarize a redacted AANA audit JSONL file.")
    audit_summary_parser.add_argument("--audit-log", required=True, help="Path to audit JSONL file.")
    audit_summary_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    audit_summary_parser.set_defaults(func=command_audit_summary)

    preflight_parser = subparsers.add_parser("production-preflight", help="Check repo-local production readiness and list external gates.")
    preflight_parser.add_argument("--deployment-manifest", default=None, help="Optional deployment manifest JSON to validate external gates.")
    preflight_parser.add_argument("--evidence-registry", default=None, help="Optional evidence registry JSON to validate evidence-source gates.")
    preflight_parser.add_argument("--observability-policy", default=None, help="Optional observability policy JSON to validate dashboard, alert, and drift-review gates.")
    preflight_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    preflight_parser.set_defaults(func=command_production_preflight)

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
    scaffold_parser.set_defaults(func=command_scaffold)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"aana_cli failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
