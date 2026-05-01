"""Small Python API for checking AI-agent events with AANA adapters."""

import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_adapter
import validate_adapter_gallery
from eval_pipeline import agent_contract, workflow_contract


AGENT_EVENT_VERSION = agent_contract.AGENT_EVENT_VERSION
WORKFLOW_CONTRACT_VERSION = workflow_contract.WORKFLOW_CONTRACT_VERSION
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AGENT_EVENTS_DIR = ROOT / "examples" / "agent_events"


POLICY_PRESETS = {
    "message_send": {
        "description": "Use before an agent sends an email, chat message, support reply, or public post.",
        "recommended_adapters": ["support_reply"],
        "call_before": ["send_message", "send_email", "publish_post"],
        "watch_for": ["private data", "unsupported claims", "tone", "missing evidence"],
    },
    "file_write": {
        "description": "Use before an agent writes, moves, deletes, or publishes user files.",
        "recommended_adapters": [],
        "call_before": ["write_file", "move_file", "delete_file", "publish_file"],
        "watch_for": ["destructive edits", "missing user confirmation", "irreversible loss"],
    },
    "code_commit": {
        "description": "Use before an agent commits, pushes, or opens a pull request.",
        "recommended_adapters": [],
        "call_before": ["git_commit", "git_push", "create_pull_request"],
        "watch_for": ["test failures", "secret leakage", "unreviewed scope", "unsafe automation"],
    },
    "support_reply": {
        "description": "Use before an agent drafts customer-support replies or account-specific messages.",
        "recommended_adapters": ["support_reply"],
        "call_before": ["draft_support_reply", "send_support_reply"],
        "watch_for": ["invented account facts", "private account data", "unsupported promises"],
    },
    "booking_or_purchase": {
        "description": "Use before an agent books, buys, reserves, or recommends paid options.",
        "recommended_adapters": ["travel_planning"],
        "call_before": ["book_trip", "purchase_item", "reserve_ticket"],
        "watch_for": ["budget caps", "forbidden transport", "missing live prices", "irreversible actions"],
    },
    "private_data_use": {
        "description": "Use before an agent reads, summarizes, shares, or acts on private user/account data.",
        "recommended_adapters": ["support_reply"],
        "call_before": ["read_private_data", "share_private_data", "summarize_account"],
        "watch_for": ["data minimization", "verified need", "secure routing", "missing consent"],
    },
    "research_summary": {
        "description": "Use before an agent publishes or shares a research summary, brief, synthesis, or cited answer.",
        "recommended_adapters": ["research_summary"],
        "call_before": ["draft_research_summary", "publish_brief", "answer_with_citations"],
        "watch_for": ["invented citations", "unsupported claims", "forbidden sources", "missing uncertainty"],
    },
}


def load_json_file(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


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


def prompt_from_event(event):
    user_request = event.get("user_request") or event.get("prompt")
    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("Agent event must include a non-empty user_request.")

    evidence = event.get("available_evidence", [])
    if isinstance(evidence, list) and evidence:
        evidence_lines = "\n".join(f"- {item}" for item in evidence)
        return f"{user_request}\n\nAvailable verified evidence:\n{evidence_lines}"
    return user_request


def candidate_from_event(event):
    candidate = event.get("candidate_action")
    if candidate is None:
        candidate = event.get("candidate_answer")
    if candidate is None:
        candidate = event.get("draft_response")
    return candidate


def check_event(event, gallery_path=DEFAULT_GALLERY, adapter_id=None):
    contract_report = agent_contract.validate_agent_event(event)
    if not contract_report["valid"]:
        messages = "; ".join(issue["message"] for issue in contract_report["issues"] if issue["level"] == "error")
        raise ValueError(messages)

    gallery = load_gallery(gallery_path)
    resolved_adapter_id = adapter_id or event.get("adapter_id") or event.get("workflow")
    if not resolved_adapter_id:
        raise ValueError("Agent event must include adapter_id or workflow, or pass adapter_id.")

    entry = find_entry(gallery, resolved_adapter_id)
    adapter = run_adapter.load_adapter(ROOT / entry["adapter_path"])
    result = run_adapter.run_adapter(adapter, prompt_from_event(event), candidate_from_event(event))
    return {
        "agent_check_version": AGENT_EVENT_VERSION,
        "agent": event.get("agent", "unknown"),
        "adapter_id": resolved_adapter_id,
        "workflow": entry.get("title"),
        "event_id": event.get("event_id"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "violations": result.get("candidate_tool_report", result.get("tool_report", {})).get("violations", []),
        "safe_response": result.get("final_answer"),
        "adapter_result": result,
    }


def check_workflow(
    adapter,
    request,
    candidate=None,
    evidence=None,
    constraints=None,
    allowed_actions=None,
    metadata=None,
    workflow_id=None,
    gallery_path=DEFAULT_GALLERY,
):
    workflow_request = workflow_contract.normalize_workflow_request(
        adapter=adapter,
        request=request,
        candidate=candidate,
        evidence=evidence,
        constraints=constraints,
        allowed_actions=allowed_actions,
        metadata=metadata,
        workflow_id=workflow_id,
    )
    return check_workflow_request(workflow_request, gallery_path=gallery_path)


def check_workflow_request(workflow_request, gallery_path=DEFAULT_GALLERY):
    contract_report = workflow_contract.validate_workflow_request(workflow_request)
    if not contract_report["valid"]:
        messages = "; ".join(issue["message"] for issue in contract_report["issues"] if issue["level"] == "error")
        raise ValueError(messages)

    event = workflow_contract.workflow_request_to_agent_event(workflow_request)
    result = check_event(event, gallery_path=gallery_path)
    recommended_action, action_violation = workflow_contract.action_within_allowed(
        result.get("recommended_action"),
        workflow_request.get("allowed_actions"),
    )
    violations = list(result.get("violations", []))
    if action_violation:
        violations.append(action_violation)
    return {
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow_request.get("workflow_id"),
        "adapter": result.get("adapter_id"),
        "workflow": result.get("workflow"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": recommended_action,
        "candidate_gate": result.get("candidate_gate"),
        "violations": violations,
        "output": result.get("safe_response"),
        "raw_result": result,
    }


def list_policy_presets():
    return POLICY_PRESETS


def validate_event(event):
    return agent_contract.validate_agent_event(event)


def validate_workflow_request(workflow_request):
    return workflow_contract.validate_workflow_request(workflow_request)


def schema_catalog():
    return {
        **agent_contract.schema_catalog(),
        **workflow_contract.schema_catalog(),
    }


def discover_agent_events(events_dir=DEFAULT_AGENT_EVENTS_DIR):
    path = pathlib.Path(events_dir)
    if not path.exists():
        raise ValueError(f"Agent events directory does not exist: {path}")
    return sorted(item for item in path.glob("*.json") if item.is_file())


def run_agent_event_examples(events_dir=DEFAULT_AGENT_EVENTS_DIR, gallery_path=DEFAULT_GALLERY):
    rows = []
    for path in discover_agent_events(events_dir):
        event = load_json_file(path)
        validation = validate_event(event)
        if not validation["valid"]:
            rows.append(
                {
                    "event_file": str(path),
                    "event_id": event.get("event_id"),
                    "adapter_id": event.get("adapter_id"),
                    "valid": False,
                    "gate_decision": None,
                    "recommended_action": None,
                    "candidate_gate": None,
                    "passed_expectations": False,
                    "validation": validation,
                }
            )
            continue

        result = check_event(event, gallery_path=gallery_path)
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        expected_candidate_gate = metadata.get("expected_candidate_gate")
        expected_gate_decision = metadata.get("expected_gate_decision")
        expected_recommended_action = metadata.get("expected_recommended_action")
        expectation_checks = [
            expected_candidate_gate is None or result.get("candidate_gate") == expected_candidate_gate,
            expected_gate_decision is None or result.get("gate_decision") == expected_gate_decision,
            expected_recommended_action is None or result.get("recommended_action") == expected_recommended_action,
        ]
        rows.append(
            {
                "event_file": str(path),
                "event_id": event.get("event_id"),
                "adapter_id": result.get("adapter_id"),
                "valid": True,
                "gate_decision": result.get("gate_decision"),
                "recommended_action": result.get("recommended_action"),
                "candidate_gate": result.get("candidate_gate"),
                "passed_expectations": all(expectation_checks),
                "validation": validation,
            }
        )

    return {
        "valid": all(row["valid"] and row["passed_expectations"] for row in rows),
        "events_dir": str(pathlib.Path(events_dir)),
        "count": len(rows),
        "checked_examples": rows,
    }


def build_agent_event_from_gallery(adapter_id, gallery_path=DEFAULT_GALLERY, agent="openclaw"):
    gallery = load_gallery(gallery_path)
    entry = find_entry(gallery, adapter_id)
    expected = entry.get("expected", {}) if isinstance(entry.get("expected"), dict) else {}
    event_id = f"draft-{adapter_id}-001"
    evidence = [
        f"Workflow: {entry.get('workflow', 'replace with verified workflow notes')}",
        "Replace this list with verified facts, records, constraints, or retrieved evidence.",
    ]
    for constraint_id in expected.get("failing_constraints", []):
        evidence.append(f"Constraint to preserve: {constraint_id}")

    return {
        "event_version": AGENT_EVENT_VERSION,
        "event_id": event_id,
        "agent": agent,
        "adapter_id": adapter_id,
        "user_request": entry.get("prompt", "Replace with the user request to check."),
        "candidate_action": entry.get("bad_candidate", "Replace with the agent's planned answer or action."),
        "available_evidence": evidence,
        "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
        "metadata": {
            "scenario": adapter_id,
            "policy_preset": suggested_policy_preset(adapter_id),
            "expected_candidate_gate": expected.get("candidate_gate"),
            "expected_gate_decision": expected.get("gate_decision"),
            "expected_recommended_action": expected.get("recommended_action"),
            "notes": "Replace starter values with a real planned agent action before production use.",
        },
    }


def suggested_policy_preset(adapter_id):
    for preset_name, preset in POLICY_PRESETS.items():
        if adapter_id in preset.get("recommended_adapters", []):
            return preset_name
    return "custom"


def scaffold_agent_event(adapter_id, output_dir=DEFAULT_AGENT_EVENTS_DIR, gallery_path=DEFAULT_GALLERY, agent="openclaw", force=False):
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{adapter_id}.json"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")

    event = build_agent_event_from_gallery(adapter_id, gallery_path=gallery_path, agent=agent)
    path.write_text(json.dumps(event, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "event": str(path),
        "next_steps": [
            f"python scripts/aana_cli.py validate-event --event {path}",
            f"python scripts/aana_cli.py agent-check --event {path}",
            "Replace the starter candidate_action and available_evidence with a real agent workflow case.",
        ],
    }
