"""Gate and repair-policy helpers shared by adapter-runner surfaces."""

try:
    from constraint_tools import is_clarification_request
except ModuleNotFoundError:  # pragma: no cover - used by script-path imports.
    from eval_pipeline.constraint_tools import is_clarification_request


REPAIR_ACTIONS = ("accept", "revise", "retrieve", "ask", "defer", "refuse")
ACTION_PRIORITY = {
    "accept": 0,
    "revise": 1,
    "retrieve": 2,
    "ask": 3,
    "defer": 4,
    "refuse": 5,
}


def gate_from_report(report):
    return "pass" if not report.get("violations") else "block"


def action_from_answer_and_report(answer, report, fallback="accept"):
    if answer and is_clarification_request(answer):
        return "ask"
    if report.get("violations"):
        return "revise"
    return fallback


def normalize_allowed_actions(allowed_actions=None):
    actions = tuple(allowed_actions or REPAIR_ACTIONS)
    unknown = sorted(set(actions) - set(REPAIR_ACTIONS))
    if unknown:
        raise ValueError("Unknown repair action(s): " + ", ".join(unknown))
    return actions


def _fallback_allowed(preferred_action, allowed_actions):
    if preferred_action in allowed_actions:
        return preferred_action, None
    for action in ("defer", "ask", "revise", "refuse", "retrieve", "accept"):
        if action in allowed_actions:
            return action, {
                "from": preferred_action,
                "to": action,
                "reason": "preferred_action_not_allowed",
            }
    raise ValueError("At least one repair action must be allowed.")


def _strictest_action(actions):
    return max(actions, key=lambda action: ACTION_PRIORITY.get(action, -1))


def decide_correction_action(
    report,
    *,
    allowed_actions=None,
    evidence_state="available",
    verifier_confidence="strong",
    fallback_action="revise",
):
    """Choose the correction route separately from verifier detection.

    Evidence and confidence fallbacks are intentionally explicit so callers can
    audit when the runtime retrieved more evidence, asked, deferred, or refused
    because it could not safely trust the available signal.
    """

    allowed = normalize_allowed_actions(allowed_actions)
    violations = list((report or {}).get("violations", []))
    routes = dict((report or {}).get("correction_routes", {}))
    unmapped = list((report or {}).get("unmapped_violations", []))

    if evidence_state in {"missing", "stale", "insufficient"}:
        preferred = "retrieve" if "retrieve" in allowed else "defer"
        action, fallback = _fallback_allowed(preferred, allowed)
        return {
            "action": action,
            "reason": "evidence_" + evidence_state,
            "source": "fallback_policy",
            "fallback": fallback,
            "allowed_actions": list(allowed),
        }

    if verifier_confidence in {"weak", "unknown", "uncalibrated"}:
        preferred = "defer"
        action, fallback = _fallback_allowed(preferred, allowed)
        return {
            "action": action,
            "reason": "verifier_confidence_" + verifier_confidence,
            "source": "fallback_policy",
            "fallback": fallback,
            "allowed_actions": list(allowed),
        }

    if not violations:
        action, fallback = _fallback_allowed("accept", allowed)
        return {
            "action": action,
            "reason": "no_violations",
            "source": "verifier_report",
            "fallback": fallback,
            "allowed_actions": list(allowed),
        }

    routed_actions = [action for action in routes.values() if action in REPAIR_ACTIONS]
    if routed_actions:
        preferred = _strictest_action(routed_actions)
        action, fallback = _fallback_allowed(preferred, allowed)
        return {
            "action": action,
            "reason": "mapped_violation_route",
            "source": "verifier_report",
            "fallback": fallback,
            "allowed_actions": list(allowed),
            "violation_routes": routes,
            "unmapped_violations": unmapped,
        }

    preferred = "defer" if unmapped else fallback_action
    action, fallback = _fallback_allowed(preferred, allowed)
    return {
        "action": action,
        "reason": "unmapped_violation" if unmapped else "default_violation_fallback",
        "source": "fallback_policy",
        "fallback": fallback,
        "allowed_actions": list(allowed),
        "violation_routes": routes,
        "unmapped_violations": unmapped,
    }
