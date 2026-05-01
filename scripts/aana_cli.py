#!/usr/bin/env python
"""Small command hub for trying and extending AANA adapters."""

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import new_adapter
import run_adapter
import validate_adapter
import validate_adapter_gallery


DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
AGENT_EVENT_VERSION = "0.1"


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


def load_json_file(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


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


def prompt_from_agent_event(event):
    user_request = event.get("user_request") or event.get("prompt")
    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("Agent event must include a non-empty user_request.")

    evidence = event.get("available_evidence", [])
    if isinstance(evidence, list) and evidence:
        evidence_lines = "\n".join(f"- {item}" for item in evidence)
        return f"{user_request}\n\nAvailable verified evidence:\n{evidence_lines}"
    return user_request


def candidate_from_agent_event(event):
    candidate = event.get("candidate_action")
    if candidate is None:
        candidate = event.get("candidate_answer")
    if candidate is None:
        candidate = event.get("draft_response")
    return candidate


def command_agent_check(args):
    event = load_json_file(args.event)
    gallery = load_gallery(args.gallery)
    adapter_id = args.adapter_id or event.get("adapter_id") or event.get("workflow")
    if not adapter_id:
        raise ValueError("Agent event must include adapter_id or workflow, or pass --adapter-id.")

    entry = find_entry(gallery, adapter_id)
    adapter = run_adapter.load_adapter(ROOT / entry["adapter_path"])
    prompt = prompt_from_agent_event(event)
    candidate = candidate_from_agent_event(event)
    result = run_adapter.run_adapter(adapter, prompt, candidate)
    response = {
        "agent_check_version": AGENT_EVENT_VERSION,
        "agent": event.get("agent", "unknown"),
        "adapter_id": adapter_id,
        "workflow": entry.get("title"),
        "event_id": event.get("event_id"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "violations": result.get("candidate_tool_report", result.get("tool_report", {})).get("violations", []),
        "safe_response": result.get("final_answer"),
        "adapter_result": result,
    }
    print_json(response)
    return 0 if response["gate_decision"] == "pass" else 1


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
