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


AGENT_EVENT_VERSION = "0.1"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"


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


def list_policy_presets():
    return POLICY_PRESETS
