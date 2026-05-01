#!/usr/bin/env python
"""Small command hub for trying and extending AANA adapters."""

import argparse
import json
import os
import pathlib
import platform
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import new_adapter
import run_adapter
import validate_adapter
import validate_adapter_gallery
from eval_pipeline import common
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
    print_json(response)
    return 0 if response["gate_decision"] == "pass" else 1


def command_workflow_check(args):
    if args.workflow:
        workflow_request = agent_api.load_json_file(args.workflow)
        result = agent_api.check_workflow_request(workflow_request, gallery_path=args.gallery)
        print_json(result)
        return 0 if result["gate_decision"] == "pass" else 1

    evidence = list(args.evidence or [])
    constraints = list(args.constraint or [])
    result = agent_api.check_workflow(
        adapter=args.adapter,
        request=args.request,
        candidate=args.candidate,
        evidence=evidence,
        constraints=constraints,
        workflow_id=args.workflow_id,
        gallery_path=args.gallery,
    )
    print_json(result)
    return 0 if result["gate_decision"] == "pass" else 1


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
    schema_ok = {"agent_event", "agent_check_result", "workflow_request", "workflow_result"}.issubset(schemas)
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
    agent_parser.set_defaults(func=command_agent_check)

    workflow_parser = subparsers.add_parser("workflow-check", help="Check a workflow request with the AANA Workflow Contract.")
    workflow_parser.add_argument("--workflow", default=None, help="Path to workflow request JSON. When provided, other workflow fields are ignored.")
    workflow_parser.add_argument("--adapter", default=None, help="Gallery adapter id, such as research_summary.")
    workflow_parser.add_argument("--request", default=None, help="User request or workflow instruction.")
    workflow_parser.add_argument("--candidate", default=None, help="Proposed output or action to check.")
    workflow_parser.add_argument("--evidence", action="append", default=[], help="Verified evidence item. Repeat as needed.")
    workflow_parser.add_argument("--constraint", action="append", default=[], help="Constraint to preserve. Repeat as needed.")
    workflow_parser.add_argument("--workflow-id", default=None, help="Optional workflow id for logs/results.")
    workflow_parser.set_defaults(func=command_workflow_check)

    validate_workflow_parser = subparsers.add_parser("validate-workflow", help="Validate an AANA workflow request JSON file.")
    validate_workflow_parser.add_argument("--workflow", required=True, help="Path to workflow request JSON.")
    validate_workflow_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    validate_workflow_parser.set_defaults(func=command_validate_workflow)

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
        choices=["all", "workflow_request", "workflow_result"],
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
