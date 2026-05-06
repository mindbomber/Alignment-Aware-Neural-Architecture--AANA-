"""Verifier registry primitives for adapter-runner report modules."""

from dataclasses import dataclass


HARD_BLOCKER_SEVERITIES = {"high", "critical"}


def normalize_verifier_report(
    checks,
    violations,
    default_route="revise",
    violation_routes=None,
    hard_blocker_severities=None,
):
    routes = violation_routes or {}
    hard_severities = hard_blocker_severities or HARD_BLOCKER_SEVERITIES
    hard_blockers = [
        violation.get("code")
        for violation in violations
        if violation.get("severity") in hard_severities and violation.get("code")
    ]
    correction_routes = {
        violation.get("code"): routes[violation.get("code")]
        for violation in violations
        if violation.get("code") in routes
    }
    unmapped_violations = [
        violation.get("code")
        for violation in violations
        if violation.get("code") and violation.get("code") not in routes
    ]
    recommended_action = default_route if violations else "accept"
    return {
        "checks": checks,
        "violations": violations,
        "tool_score": 0.0 if violations else 1.0,
        "recommended_action": recommended_action,
        "hard_blockers": hard_blockers,
        "correction_routes": correction_routes,
        "unmapped_violations": unmapped_violations,
    }


@dataclass(frozen=True)
class VerifierModule:
    name: str
    report_function: object
    family: str = "uncategorized"
    supported_adapters: object = None
    adapter_predicate: object = None
    safe_response_function: object = None
    detection_function: object = None
    route_policy: object = None
    correction_routes: object = None
    fallback_action: str = "revise"

    def run(self, prompt, answer):
        return self.report_function(prompt, answer)


class VerifierRegistry:
    def __init__(self, modules=()):
        self._modules = {module.name: module for module in modules}

    def register(
        self,
        name,
        report_function,
        family="uncategorized",
        supported_adapters=None,
        adapter_predicate=None,
        safe_response_function=None,
        detection_function=None,
        route_policy=None,
        correction_routes=None,
        fallback_action="revise",
    ):
        self._modules[name] = VerifierModule(
            name=name,
            report_function=report_function,
            family=family,
            supported_adapters=supported_adapters or (),
            adapter_predicate=adapter_predicate,
            safe_response_function=safe_response_function,
            detection_function=detection_function,
            route_policy=route_policy,
            correction_routes=correction_routes,
            fallback_action=fallback_action,
        )

    def names(self):
        return sorted(self._modules)

    def get(self, name):
        return self._modules[name]


def build_verifier_registry(modules):
    registry = VerifierRegistry()
    for name, spec in modules.items():
        if callable(spec):
            registry.register(name, spec)
            continue
        spec = dict(spec)
        report_function = spec.pop("report_function")
        registry.register(name, report_function, **spec)
    return registry
