"""Production deployment manifest checks for AANA."""


REQUIRED_TOP_LEVEL = [
    "deployment_name",
    "environment",
    "bridge",
    "audit",
    "evidence_sources",
    "observability",
    "domain_owners",
    "human_review",
]

REQUIRED_DEPLOYMENT_TOP_LEVEL = {
    "container",
    "kubernetes",
    "incident_response",
}

REQUIRED_GOVERNANCE_TOP_LEVEL = [
    "policy_name",
    "owner",
    "review_cadence",
    "escalation_classes",
    "decision_explanations",
    "review_metrics",
    "incident_response",
]

REQUIRED_OBSERVABILITY_TOP_LEVEL = [
    "policy_name",
    "owner",
    "dashboard_url",
    "dashboards",
    "tracked_metrics",
    "alerts",
    "drift_review",
    "latency_slo",
    "on_call",
]

REQUIRED_OBSERVABILITY_METRICS = {
    "aix_decision_count",
    "aix_hard_blocker_count",
    "aix_score_average",
    "connector_failure_count",
    "evidence_freshness_failure_count",
    "gate_decision_count",
    "recommended_action_count",
    "refusal_defer_rate",
    "violation_code_count",
    "latency",
}

REQUIRED_OBSERVABILITY_ALERTS = {
    "high_refusal_defer_rate",
    "connector_failures",
    "stale_evidence",
    "latency_spike",
    "aix_drift",
    "hard_blocker_spike",
}

REQUIRED_OBSERVABILITY_DASHBOARD_PANELS = {
    "gate_decisions",
    "recommended_actions",
    "refusal_defer_rate",
    "connector_failures",
    "evidence_freshness",
    "latency",
    "aix_drift",
    "hard_blockers",
}

DEFAULT_ALLOWED_AIX_DECISIONS = {"accept", "revise"}


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder(value):
    return isinstance(value, str) and "replace" in value.lower()


def _add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def validate_deployment_manifest(manifest):
    issues = []
    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "Deployment manifest must be a JSON object."}],
        }

    for key in REQUIRED_TOP_LEVEL:
        if key not in manifest:
            _add_issue(issues, "error", f"$.{key}", "Required deployment field is missing.")
    for key in REQUIRED_DEPLOYMENT_TOP_LEVEL:
        if key not in manifest:
            _add_issue(issues, "error", f"$.{key}", "Required deployment-hardening field is missing.")

    for key in ("deployment_name", "environment"):
        if key in manifest and not _has_text(manifest.get(key)):
            _add_issue(issues, "error", f"$.{key}", "Field must be a non-empty string.")

    bridge = manifest.get("bridge", {})
    if isinstance(bridge, dict):
        if bridge.get("auth_required") is not True:
            _add_issue(issues, "error", "$.bridge.auth_required", "Production bridge must require authentication.")
        if bridge.get("tls_terminated") is not True:
            _add_issue(issues, "error", "$.bridge.tls_terminated", "Production bridge must run behind TLS termination.")
        tls = bridge.get("tls", {})
        if not isinstance(tls, dict):
            _add_issue(issues, "error", "$.bridge.tls", "TLS assumptions must be an object.")
        else:
            for key in ("termination", "ingress_class", "certificate_ref", "minimum_tls_version"):
                value = tls.get(key)
                if not _has_text(value) or _is_placeholder(value):
                    _add_issue(issues, "error", f"$.bridge.tls.{key}", "TLS/ingress assumption must be concrete.")
            if tls.get("https_only") is not True:
                _add_issue(issues, "error", "$.bridge.tls.https_only", "Ingress must enforce HTTPS-only access.")
        if not isinstance(bridge.get("max_body_bytes"), int) or bridge.get("max_body_bytes") <= 0:
            _add_issue(issues, "error", "$.bridge.max_body_bytes", "max_body_bytes must be a positive integer.")
        rate_limits = bridge.get("rate_limits", {})
        if not isinstance(rate_limits, dict) or rate_limits.get("enabled") is not True:
            _add_issue(issues, "error", "$.bridge.rate_limits.enabled", "Production bridge must declare enabled rate limits.")
        else:
            for key in ("requests_per_minute", "burst"):
                if not isinstance(rate_limits.get(key), int) or rate_limits.get(key) <= 0:
                    _add_issue(issues, "error", f"$.bridge.rate_limits.{key}", "Rate limit value must be a positive integer.")
            if rate_limits.get("runtime_enforced") is not True:
                _add_issue(issues, "error", "$.bridge.rate_limits.runtime_enforced", "Runtime rate limiting must be enabled.")
            if rate_limits.get("edge_enforced") is not True:
                _add_issue(issues, "error", "$.bridge.rate_limits.edge_enforced", "Edge rate limiting must be enabled.")
    elif "bridge" in manifest:
        _add_issue(issues, "error", "$.bridge", "bridge must be an object.")

    container = manifest.get("container", {})
    if isinstance(container, dict):
        for key in ("image", "image_pull_policy", "command"):
            value = container.get(key)
            if not _has_text(value) or _is_placeholder(value):
                _add_issue(issues, "error", f"$.container.{key}", "Container deployment field must be concrete.")
        probes = container.get("probes", {})
        if not isinstance(probes, dict):
            _add_issue(issues, "error", "$.container.probes", "Container probes must be an object.")
        else:
            for key, expected_path in (("liveness", "/health"), ("readiness", "/ready")):
                probe = probes.get(key, {})
                if not isinstance(probe, dict):
                    _add_issue(issues, "error", f"$.container.probes.{key}", "Probe must be an object.")
                    continue
                if probe.get("path") != expected_path:
                    _add_issue(issues, "error", f"$.container.probes.{key}.path", f"Probe path must be {expected_path}.")
                if not isinstance(probe.get("period_seconds"), int) or probe.get("period_seconds") <= 0:
                    _add_issue(issues, "error", f"$.container.probes.{key}.period_seconds", "Probe period must be positive.")
        resources = container.get("resources", {})
        if not isinstance(resources, dict):
            _add_issue(issues, "error", "$.container.resources", "Container resources must be an object.")
        else:
            for section in ("requests", "limits"):
                values = resources.get(section, {})
                if not isinstance(values, dict):
                    _add_issue(issues, "error", f"$.container.resources.{section}", "Resource section must be an object.")
                    continue
                for key in ("cpu", "memory"):
                    value = values.get(key)
                    if not _has_text(value) or _is_placeholder(value):
                        _add_issue(issues, "error", f"$.container.resources.{section}.{key}", "Resource value must be concrete.")
    elif "container" in manifest:
        _add_issue(issues, "error", "$.container", "container must be an object.")

    kubernetes = manifest.get("kubernetes", {})
    if isinstance(kubernetes, dict):
        for key in ("manifest", "namespace", "service_name", "ingress_name", "rollback_command"):
            value = kubernetes.get(key)
            if not _has_text(value) or _is_placeholder(value):
                _add_issue(issues, "error", f"$.kubernetes.{key}", "Kubernetes deployment field must be concrete.")
        if kubernetes.get("health_endpoint") != "/health":
            _add_issue(issues, "error", "$.kubernetes.health_endpoint", "health_endpoint must be /health.")
        if kubernetes.get("readiness_endpoint") != "/ready":
            _add_issue(issues, "error", "$.kubernetes.readiness_endpoint", "readiness_endpoint must be /ready.")
    elif "kubernetes" in manifest:
        _add_issue(issues, "error", "$.kubernetes", "kubernetes must be an object.")

    incident_response = manifest.get("incident_response", {})
    if isinstance(incident_response, dict):
        for key in ("owner", "incident_channel", "rollback_path", "rollback_trigger", "last_known_good_artifact"):
            value = incident_response.get(key)
            if not _has_text(value) or _is_placeholder(value):
                _add_issue(issues, "error", f"$.incident_response.{key}", "Incident rollback field must be concrete.")
        steps = incident_response.get("rollback_steps")
        if not isinstance(steps, list) or not steps:
            _add_issue(issues, "error", "$.incident_response.rollback_steps", "Rollback steps must be a non-empty list.")
    elif "incident_response" in manifest:
        _add_issue(issues, "error", "$.incident_response", "incident_response must be an object.")

    audit = manifest.get("audit", {})
    if isinstance(audit, dict):
        if not _has_text(audit.get("sink")) or _is_placeholder(audit.get("sink")):
            _add_issue(issues, "error", "$.audit.sink", "Audit sink must name a real append-only destination.")
        if audit.get("immutable") is not True:
            _add_issue(issues, "error", "$.audit.immutable", "Audit sink must be immutable or append-only.")
        if audit.get("redaction_required") is not True:
            _add_issue(issues, "error", "$.audit.redaction_required", "Audit records must require redaction.")
        if not isinstance(audit.get("retention_days"), int) or audit.get("retention_days") <= 0:
            _add_issue(issues, "error", "$.audit.retention_days", "retention_days must be a positive integer.")
    elif "audit" in manifest:
        _add_issue(issues, "error", "$.audit", "audit must be an object.")

    evidence_sources = manifest.get("evidence_sources", [])
    if not isinstance(evidence_sources, list) or not evidence_sources:
        _add_issue(issues, "error", "$.evidence_sources", "At least one evidence source is required.")
    else:
        for index, source in enumerate(evidence_sources):
            if not isinstance(source, dict):
                _add_issue(issues, "error", f"$.evidence_sources[{index}]", "Evidence source must be an object.")
                continue
            for key in ("source_id", "owner", "authorization", "freshness_slo", "trust_tier"):
                value = source.get(key)
                if not _has_text(value) or _is_placeholder(value):
                    _add_issue(issues, "error", f"$.evidence_sources[{index}].{key}", "Evidence source field must be concrete.")

    observability = manifest.get("observability", {})
    if isinstance(observability, dict):
        if not _has_text(observability.get("dashboard_url")) or _is_placeholder(observability.get("dashboard_url")):
            _add_issue(issues, "warning", "$.observability.dashboard_url", "Dashboard URL should be concrete before launch.")
        if observability.get("alerts_enabled") is not True:
            _add_issue(issues, "error", "$.observability.alerts_enabled", "Production observability must enable alerts.")
        tracked_metrics = observability.get("tracked_metrics")
        if not isinstance(tracked_metrics, list) or not tracked_metrics:
            _add_issue(issues, "error", "$.observability.tracked_metrics", "At least one tracked metric is required.")
        else:
            missing = sorted(REQUIRED_OBSERVABILITY_METRICS - set(tracked_metrics))
            if missing:
                _add_issue(
                    issues,
                    "error",
                    "$.observability.tracked_metrics",
                    "tracked_metrics is missing required production metrics: " + ", ".join(missing),
                )
    elif "observability" in manifest:
        _add_issue(issues, "error", "$.observability", "observability must be an object.")

    domain_owners = manifest.get("domain_owners", [])
    if not isinstance(domain_owners, list) or not domain_owners:
        _add_issue(issues, "error", "$.domain_owners", "At least one domain owner entry is required.")
    else:
        for index, owner in enumerate(domain_owners):
            if not isinstance(owner, dict):
                _add_issue(issues, "error", f"$.domain_owners[{index}]", "Domain owner must be an object.")
                continue
            for key in ("adapter_id", "owner"):
                value = owner.get(key)
                if not _has_text(value) or _is_placeholder(value):
                    _add_issue(issues, "error", f"$.domain_owners[{index}].{key}", "Domain owner field must be concrete.")
            if owner.get("review_status") not in {"approved", "pilot_approved"}:
                _add_issue(issues, "error", f"$.domain_owners[{index}].review_status", "review_status must be approved or pilot_approved.")

    human_review = manifest.get("human_review", {})
    if isinstance(human_review, dict):
        if not _has_text(human_review.get("queue")) or _is_placeholder(human_review.get("queue")):
            _add_issue(issues, "error", "$.human_review.queue", "Human review queue must be concrete.")
        if not isinstance(human_review.get("required_for"), list) or not human_review.get("required_for"):
            _add_issue(issues, "error", "$.human_review.required_for", "Human review triggers are required.")
        if not _has_text(human_review.get("sla")) or _is_placeholder(human_review.get("sla")):
            _add_issue(issues, "warning", "$.human_review.sla", "Human review SLA should be concrete before launch.")
    elif "human_review" in manifest:
        _add_issue(issues, "error", "$.human_review", "human_review must be an object.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def validate_governance_policy(policy):
    issues = []
    if not isinstance(policy, dict):
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "Governance policy must be a JSON object."}],
        }

    for key in REQUIRED_GOVERNANCE_TOP_LEVEL:
        if key not in policy:
            _add_issue(issues, "error", f"$.{key}", "Required governance field is missing.")

    for key in ("policy_name", "owner", "review_cadence"):
        value = policy.get(key)
        if key in policy and (not _has_text(value) or _is_placeholder(value)):
            _add_issue(issues, "error", f"$.{key}", "Governance field must be concrete.")

    escalation_classes = policy.get("escalation_classes", [])
    if not isinstance(escalation_classes, list) or not escalation_classes:
        _add_issue(issues, "error", "$.escalation_classes", "At least one escalation class is required.")
    else:
        for index, item in enumerate(escalation_classes):
            if not isinstance(item, dict):
                _add_issue(issues, "error", f"$.escalation_classes[{index}]", "Escalation class must be an object.")
                continue
            for key in ("name", "trigger", "route", "allowed_actions"):
                if key not in item:
                    _add_issue(issues, "error", f"$.escalation_classes[{index}].{key}", "Escalation class field is required.")
            for key in ("name", "trigger", "route"):
                value = item.get(key)
                if key in item and (not _has_text(value) or _is_placeholder(value)):
                    _add_issue(issues, "error", f"$.escalation_classes[{index}].{key}", "Escalation class field must be concrete.")
            actions = item.get("allowed_actions")
            if not isinstance(actions, list) or not actions:
                _add_issue(issues, "error", f"$.escalation_classes[{index}].allowed_actions", "allowed_actions must be a non-empty list.")

    decision_explanations = policy.get("decision_explanations", {})
    if isinstance(decision_explanations, dict):
        for action in ("ask", "defer", "refuse"):
            value = decision_explanations.get(action)
            if not _has_text(value) or _is_placeholder(value):
                _add_issue(issues, "error", f"$.decision_explanations.{action}", f"Explanation template for {action} must be concrete.")
    elif "decision_explanations" in policy:
        _add_issue(issues, "error", "$.decision_explanations", "decision_explanations must be an object.")

    review_metrics = policy.get("review_metrics", [])
    if not isinstance(review_metrics, list) or not review_metrics:
        _add_issue(issues, "error", "$.review_metrics", "At least one review metric is required.")
    elif any(not _has_text(item) or _is_placeholder(item) for item in review_metrics):
        _add_issue(issues, "error", "$.review_metrics", "Review metrics must be concrete strings.")

    incident_response = policy.get("incident_response", {})
    if isinstance(incident_response, dict):
        for key in ("owner", "severity_levels", "rollback_trigger", "notification_path"):
            if key not in incident_response:
                _add_issue(issues, "error", f"$.incident_response.{key}", "Incident response field is required.")
        for key in ("owner", "rollback_trigger", "notification_path"):
            value = incident_response.get(key)
            if key in incident_response and (not _has_text(value) or _is_placeholder(value)):
                _add_issue(issues, "error", f"$.incident_response.{key}", "Incident response field must be concrete.")
        levels = incident_response.get("severity_levels")
        if "severity_levels" in incident_response and (not isinstance(levels, list) or not levels):
            _add_issue(issues, "error", "$.incident_response.severity_levels", "severity_levels must be a non-empty list.")
    elif "incident_response" in policy:
        _add_issue(issues, "error", "$.incident_response", "incident_response must be an object.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def validate_observability_policy(policy):
    issues = []
    if not isinstance(policy, dict):
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "Observability policy must be a JSON object."}],
        }

    for key in REQUIRED_OBSERVABILITY_TOP_LEVEL:
        if key not in policy:
            _add_issue(issues, "error", f"$.{key}", "Required observability field is missing.")

    for key in ("policy_name", "owner", "dashboard_url"):
        value = policy.get(key)
        if key in policy and (not _has_text(value) or _is_placeholder(value)):
            _add_issue(issues, "error", f"$.{key}", "Observability field must be concrete.")

    dashboards = policy.get("dashboards", [])
    if not isinstance(dashboards, list) or not dashboards:
        _add_issue(issues, "error", "$.dashboards", "At least one concrete dashboard definition is required.")
    else:
        panel_ids = set()
        for index, dashboard in enumerate(dashboards):
            base = f"$.dashboards[{index}]"
            if not isinstance(dashboard, dict):
                _add_issue(issues, "error", base, "Dashboard must be an object.")
                continue
            for key in ("id", "title", "url", "metrics_source", "owner"):
                value = dashboard.get(key)
                if not _has_text(value) or _is_placeholder(value):
                    _add_issue(issues, "error", f"{base}.{key}", "Dashboard field must be concrete.")
            panels = dashboard.get("panels")
            if not isinstance(panels, list) or not panels:
                _add_issue(issues, "error", f"{base}.panels", "Dashboard must define panels.")
                continue
            for panel_index, panel in enumerate(panels):
                panel_base = f"{base}.panels[{panel_index}]"
                if not isinstance(panel, dict):
                    _add_issue(issues, "error", panel_base, "Dashboard panel must be an object.")
                    continue
                panel_id = panel.get("id")
                if _has_text(panel_id):
                    panel_ids.add(panel_id)
                for key in ("id", "title", "metric"):
                    value = panel.get(key)
                    if not _has_text(value) or _is_placeholder(value):
                        _add_issue(issues, "error", f"{panel_base}.{key}", "Dashboard panel field must be concrete.")
        missing_panels = sorted(REQUIRED_OBSERVABILITY_DASHBOARD_PANELS - panel_ids)
        if missing_panels:
            _add_issue(issues, "error", "$.dashboards", "dashboards missing required panels: " + ", ".join(missing_panels))

    tracked_metrics = policy.get("tracked_metrics", [])
    if not isinstance(tracked_metrics, list) or not tracked_metrics:
        _add_issue(issues, "error", "$.tracked_metrics", "tracked_metrics must be a non-empty list.")
    else:
        missing = sorted(REQUIRED_OBSERVABILITY_METRICS - set(tracked_metrics))
        if missing:
            _add_issue(
                issues,
                "error",
                "$.tracked_metrics",
                "tracked_metrics is missing required metrics: " + ", ".join(missing),
            )
        if any(not _has_text(item) or _is_placeholder(item) for item in tracked_metrics):
            _add_issue(issues, "error", "$.tracked_metrics", "tracked_metrics must contain concrete strings.")

    alerts = policy.get("alerts", [])
    if not isinstance(alerts, list) or not alerts:
        _add_issue(issues, "error", "$.alerts", "At least one alert is required.")
    else:
        for index, alert in enumerate(alerts):
            base = f"$.alerts[{index}]"
            if not isinstance(alert, dict):
                _add_issue(issues, "error", base, "Alert must be an object.")
                continue
            for key in ("id", "name", "metric", "condition", "severity", "route", "owner"):
                value = alert.get(key)
                if not _has_text(value) or _is_placeholder(value):
                    _add_issue(issues, "error", f"{base}.{key}", "Alert field must be concrete.")
            if "threshold" not in alert:
                _add_issue(issues, "error", f"{base}.threshold", "Alert threshold is required.")
            elif not isinstance(alert.get("threshold"), (int, float)):
                _add_issue(issues, "error", f"{base}.threshold", "Alert threshold must be numeric.")
        alert_ids = {alert.get("id") for alert in alerts if isinstance(alert, dict)}
        missing_alerts = sorted(REQUIRED_OBSERVABILITY_ALERTS - alert_ids)
        if missing_alerts:
            _add_issue(issues, "error", "$.alerts", "alerts missing required operational coverage: " + ", ".join(missing_alerts))

    drift_review = policy.get("drift_review", {})
    if isinstance(drift_review, dict):
        for key in ("cadence", "owner", "required_reports"):
            if key not in drift_review:
                _add_issue(issues, "error", f"$.drift_review.{key}", "Drift review field is required.")
        for key in ("cadence", "owner"):
            value = drift_review.get(key)
            if key in drift_review and (not _has_text(value) or _is_placeholder(value)):
                _add_issue(issues, "error", f"$.drift_review.{key}", "Drift review field must be concrete.")
        reports = drift_review.get("required_reports")
        if "required_reports" in drift_review and (not isinstance(reports, list) or not reports):
            _add_issue(issues, "error", "$.drift_review.required_reports", "required_reports must be a non-empty list.")
    elif "drift_review" in policy:
        _add_issue(issues, "error", "$.drift_review", "drift_review must be an object.")

    latency_slo = policy.get("latency_slo", {})
    if isinstance(latency_slo, dict):
        for key in ("p95_ms", "route"):
            if key not in latency_slo:
                _add_issue(issues, "error", f"$.latency_slo.{key}", "Latency SLO field is required.")
        if "p95_ms" in latency_slo and (not isinstance(latency_slo.get("p95_ms"), int) or latency_slo.get("p95_ms") <= 0):
            _add_issue(issues, "error", "$.latency_slo.p95_ms", "p95_ms must be a positive integer.")
        route = latency_slo.get("route")
        if "route" in latency_slo and (not _has_text(route) or _is_placeholder(route)):
            _add_issue(issues, "error", "$.latency_slo.route", "Latency route must be concrete.")
    elif "latency_slo" in policy:
        _add_issue(issues, "error", "$.latency_slo", "latency_slo must be an object.")

    on_call = policy.get("on_call", {})
    if isinstance(on_call, dict):
        for key in ("primary", "secondary", "schedule", "escalation_policy", "handoff", "incident_channel"):
            value = on_call.get(key)
            if not _has_text(value) or _is_placeholder(value):
                _add_issue(issues, "error", f"$.on_call.{key}", "On-call field must be concrete.")
        if "page_for" in on_call and (not isinstance(on_call.get("page_for"), list) or not on_call.get("page_for")):
            _add_issue(issues, "error", "$.on_call.page_for", "page_for must be a non-empty list when present.")
    elif "on_call" in policy:
        _add_issue(issues, "error", "$.on_call", "on_call must be an object.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def validate_aix_audit_metrics(
    metrics_export,
    min_average_score=0.85,
    min_min_score=0.5,
    max_hard_blockers=0,
    allowed_decisions=None,
):
    issues = []
    allowed = set(allowed_decisions or DEFAULT_ALLOWED_AIX_DECISIONS)
    if not isinstance(metrics_export, dict):
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "AIx metrics export must be a JSON object."}],
        }

    record_count = metrics_export.get("record_count")
    if not isinstance(record_count, int) or record_count <= 0:
        _add_issue(issues, "error", "$.record_count", "Release audit log must contain at least one record.")

    metrics = metrics_export.get("metrics")
    if not isinstance(metrics, dict):
        _add_issue(issues, "error", "$.metrics", "Metrics export must include a metrics object.")
        metrics = {}

    average_score = metrics.get("aix_score_average")
    if not isinstance(average_score, (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_average", "AIx average score is missing from audit metrics.")
    elif average_score < min_average_score:
        _add_issue(
            issues,
            "error",
            "$.metrics.aix_score_average",
            f"AIx average score {average_score} is below release threshold {min_average_score}.",
        )

    min_score = metrics.get("aix_score_min")
    if not isinstance(min_score, (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_min", "AIx minimum score is missing from audit metrics.")
    elif min_score < min_min_score:
        _add_issue(
            issues,
            "error",
            "$.metrics.aix_score_min",
            f"AIx minimum score {min_score} is below release threshold {min_min_score}.",
        )

    hard_blockers = metrics.get("aix_hard_blocker_count")
    if not isinstance(hard_blockers, int):
        _add_issue(issues, "error", "$.metrics.aix_hard_blocker_count", "AIx hard-blocker count is missing from audit metrics.")
    elif hard_blockers > max_hard_blockers:
        _add_issue(
            issues,
            "error",
            "$.metrics.aix_hard_blocker_count",
            f"AIx hard-blocker count {hard_blockers} exceeds release threshold {max_hard_blockers}.",
        )

    decision_total = metrics.get("aix_decision_count")
    if not isinstance(decision_total, int):
        _add_issue(issues, "error", "$.metrics.aix_decision_count", "AIx decision count is missing from audit metrics.")
    elif decision_total <= 0:
        _add_issue(issues, "error", "$.metrics.aix_decision_count", "Release audit log must include at least one AIx decision.")

    unexpected_decisions = {}
    for key, value in metrics.items():
        if not key.startswith("aix_decision_count.") or not isinstance(value, int) or value <= 0:
            continue
        decision = key.removeprefix("aix_decision_count.")
        if decision not in allowed:
            unexpected_decisions[decision] = value
    if unexpected_decisions:
        decisions = ", ".join(f"{key}={value}" for key, value in sorted(unexpected_decisions.items()))
        _add_issue(
            issues,
            "error",
            "$.metrics.aix_decision_count",
            f"AIx decision drift includes disallowed release decisions: {decisions}.",
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "thresholds": {
            "min_average_score": min_average_score,
            "min_min_score": min_min_score,
            "max_hard_blockers": max_hard_blockers,
            "allowed_decisions": sorted(allowed),
        },
        "record_count": record_count if isinstance(record_count, int) else 0,
    }
