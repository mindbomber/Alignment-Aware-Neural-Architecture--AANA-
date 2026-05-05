"""Production certification gates for AANA deployments."""

from __future__ import annotations

import datetime
import pathlib

from eval_pipeline import agent_api, evidence_integrations, production


PRODUCTION_CERTIFICATION_VERSION = "0.1"
EXTERNAL_EVIDENCE_VERSION = "0.1"
CONSERVATIVE_PRODUCTION_POSITIONING = (
    "This repository is demo-ready and pilot-ready for controlled evaluation, but it is not "
    "production-certified by itself. Production readiness requires live evidence connectors, "
    "domain owner signoff, audit retention, observability, and human review paths."
)
BOUNDARY_CHECKER_LINE = (
    "production-certify is a boundary checker, not a production guarantee. It separates repo-local "
    "readiness from deployment readiness and requires external evidence before production claims."
)
REQUIRED_EXTERNAL_EVIDENCE_ARTIFACTS = (
    "connector_manifests",
    "shadow_mode_logs",
    "audit_retention_policy",
    "escalation_policy",
    "owner_approval",
)
MIN_SHADOW_DURATION_DAYS = 14
MIN_SHADOW_RECORDS = 100
MIN_AUDIT_RETENTION_DAYS = 365
REQUIRED_PRODUCTION_METRICS = {
    "adapter_error_count",
    "aix_decision_count",
    "aix_hard_blocker_count",
    "aix_score_average",
    "false_accept_rate",
    "false_block_rate",
    "gate_decision_count",
    "human_review_turnaround_time",
    "latency",
    "over_refusal_rate",
    "recommended_action_count",
    "shadow_records_total",
    "shadow_would_action_count",
    "violation_code_count",
}
REQUIRED_HUMAN_REVIEW_TOPICS = {
    "high-impact",
    "low-confidence",
    "irreversible",
}
FAMILY_CERTIFICATION_GATES = {
    "enterprise": [
        "connector_freshness",
        "human_review_routing",
        "audit_retention",
        "aix_thresholds",
        "shadow_mode_pass_window",
        "production_readiness_score",
    ],
    "personal_productivity": [
        "local_only_default",
        "no_irreversible_action_without_approval",
        "redacted_audit",
        "shadow_mode_available",
        "exportable_report",
    ],
    "government_civic": [
        "source_law_traceability",
        "jurisdiction_labeling",
        "privacy_redaction",
        "mandatory_human_review",
        "public_records_retention_policy",
    ],
}


def readiness_boundary():
    return {
        "demo": {
            "purpose": "Public understanding and adapter walkthroughs.",
            "data": "Synthetic-only examples.",
            "side_effects": "No real sends, deletes, deploys, payments, bookings, permission changes, or exports.",
            "certification_line": "Demo-ready is not production-certified; it uses synthetic examples and does not require live evidence connectors, shadow-mode traffic, or production audit retention.",
        },
        "pilot": {
            "purpose": "Evaluate workflow value with synthetic, public, or tightly scoped redacted data.",
            "data": "No private production data unless approved for a controlled pilot.",
            "side_effects": "Shadow mode or advisory mode preferred; enforcement requires local owner approval.",
            "certification_line": "Pilot-ready supports controlled evaluation, but it is not production-certified without domain owner signoff and deployment evidence.",
        },
        "production": {
            "purpose": "Enforced gate in front of real user or business actions.",
            "data": "Authorized production evidence connectors with freshness, redaction, and failure-mode contracts.",
            "side_effects": "Blocking or routing decisions may affect live workflows only after certification gates pass.",
            "certification_line": "Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, human-review routing, and shadow-mode evidence.",
        },
    }


def certification_program_matrix():
    """Public matrix that distinguishes demo, pilot, and production readiness."""

    boundary = readiness_boundary()
    return {
        "production_certification_version": PRODUCTION_CERTIFICATION_VERSION,
        "production_positioning": CONSERVATIVE_PRODUCTION_POSITIONING,
        "certification_scope": BOUNDARY_CHECKER_LINE,
        "levels": {
            "demo_ready": {
                "boundary": boundary["demo"],
                "required_gates": ["synthetic_only", "no_live_actions", "no_user_secrets"],
            },
            "pilot_ready": {
                "boundary": boundary["pilot"],
                "required_gates": [
                    "family_packaged",
                    "redacted_telemetry",
                    "shadow_or_advisory_mode",
                    "starter_kit_metrics",
                ],
            },
            "production_ready": {
                "boundary": boundary["production"],
                "required_gates": sorted(
                    {
                        "external_connector_manifests",
                        "shadow_mode_minimum_duration",
                        "external_shadow_mode_logs",
                        "required_metrics",
                        "human_review_routing",
                        "connector_evidence",
                        "audit_retention",
                        "audit_retention_policy",
                        "domain_owner_signoff",
                        "owner_approval",
                    }
                ),
            },
        },
        "families": {
            family: {
                "required_gates": gates,
                "certification_line": "Family gates must pass in addition to the readiness-level gates.",
            }
            for family, gates in FAMILY_CERTIFICATION_GATES.items()
        },
    }


def _add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def _object(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _count_issues(issues):
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return errors, warnings


def _result(valid, issues, extra=None):
    errors, warnings = _count_issues(issues)
    payload = {
        "valid": valid,
        "production_ready": valid and errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }
    if extra:
        payload.update(extra)
    return payload


def validate_external_evidence_manifest(manifest, certification_policy=None):
    """Validate explicit external evidence required before production claims."""

    issues = []
    if not isinstance(manifest, dict):
        return _result(
            False,
            [{"level": "error", "path": "$", "message": "External production evidence must be a JSON object."}],
        )
    if manifest.get("external_evidence_version") != EXTERNAL_EVIDENCE_VERSION:
        _add_issue(
            issues,
            "error",
            "$.external_evidence_version",
            f"external_evidence_version must be {EXTERNAL_EVIDENCE_VERSION}.",
        )
    if manifest.get("evidence_scope") != "external_deployment":
        _add_issue(
            issues,
            "error",
            "$.evidence_scope",
            "evidence_scope must be external_deployment; repo templates and local fixtures are not production evidence.",
        )

    required_connectors = set()
    if certification_policy:
        required_connectors = set(_list(_object(certification_policy.get("connector_evidence")).get("required_connectors")))
    connector_manifests = _list(manifest.get("connector_manifests"))
    connector_ids = {
        item.get("connector_id")
        for item in connector_manifests
        if isinstance(item, dict) and _has_text(item.get("connector_id"))
    }
    if not connector_manifests:
        _add_issue(issues, "error", "$.connector_manifests", "At least one external connector manifest is required.")
    missing_connectors = sorted(required_connectors - connector_ids)
    if missing_connectors:
        _add_issue(
            issues,
            "error",
            "$.connector_manifests",
            "External connector manifests are missing required connectors: " + ", ".join(missing_connectors),
        )
    for index, item in enumerate(connector_manifests):
        if not isinstance(item, dict):
            _add_issue(issues, "error", f"$.connector_manifests[{index}]", "Connector manifest entries must be objects.")
            continue
        for key in ("connector_id", "manifest_uri", "owner", "auth_boundary", "freshness_slo", "redaction_policy"):
            if not _has_text(item.get(key)):
                _add_issue(issues, "error", f"$.connector_manifests[{index}].{key}", f"{key} is required.")
        if item.get("environment") != "production":
            _add_issue(issues, "error", f"$.connector_manifests[{index}].environment", "environment must be production.")
        if not _list(item.get("failure_modes")):
            _add_issue(issues, "error", f"$.connector_manifests[{index}].failure_modes", "failure_modes are required.")

    shadow_logs = _object(manifest.get("shadow_mode_logs"))
    if not _has_text(shadow_logs.get("audit_log_uri")):
        _add_issue(issues, "error", "$.shadow_mode_logs.audit_log_uri", "External shadow-mode audit log URI is required.")
    if shadow_logs.get("environment") != "production":
        _add_issue(issues, "error", "$.shadow_mode_logs.environment", "Shadow-mode logs must come from production.")
    if shadow_logs.get("redacted") is not True:
        _add_issue(issues, "error", "$.shadow_mode_logs.redacted", "Shadow-mode logs must be redacted.")
    if not _has_text(shadow_logs.get("retention_policy_ref")):
        _add_issue(issues, "error", "$.shadow_mode_logs.retention_policy_ref", "Shadow logs must reference retention policy.")

    audit_policy = _object(manifest.get("audit_retention_policy"))
    if not _has_text(audit_policy.get("policy_uri")):
        _add_issue(issues, "error", "$.audit_retention_policy.policy_uri", "Audit retention policy URI is required.")
    retention_days = audit_policy.get("retention_days")
    if not isinstance(retention_days, int) or retention_days < MIN_AUDIT_RETENTION_DAYS:
        _add_issue(
            issues,
            "error",
            "$.audit_retention_policy.retention_days",
            f"External audit retention must be at least {MIN_AUDIT_RETENTION_DAYS} days.",
        )
    if audit_policy.get("immutable") is not True:
        _add_issue(issues, "error", "$.audit_retention_policy.immutable", "External audit retention must be immutable or append-only.")
    if not _has_text(audit_policy.get("owner")):
        _add_issue(issues, "error", "$.audit_retention_policy.owner", "Audit retention owner is required.")

    escalation_policy = _object(manifest.get("escalation_policy"))
    if not _has_text(escalation_policy.get("policy_uri")):
        _add_issue(issues, "error", "$.escalation_policy.policy_uri", "Escalation policy URI is required.")
    if not _has_text(escalation_policy.get("human_review_queue")):
        _add_issue(issues, "error", "$.escalation_policy.human_review_queue", "Human-review queue is required.")
    covers = " ".join(str(item).lower() for item in _list(escalation_policy.get("covers")))
    for topic in sorted(REQUIRED_HUMAN_REVIEW_TOPICS):
        if topic not in covers:
            _add_issue(issues, "error", "$.escalation_policy.covers", f"Escalation policy must cover {topic} decisions.")
    if not _has_text(escalation_policy.get("owner")):
        _add_issue(issues, "error", "$.escalation_policy.owner", "Escalation policy owner is required.")

    approval = _object(manifest.get("owner_approval"))
    for key in ("approval_uri", "domain_owner", "approved_at", "scope"):
        if not _has_text(approval.get(key)):
            _add_issue(issues, "error", f"$.owner_approval.{key}", f"{key} is required.")
    if approval.get("scope") != "production":
        _add_issue(issues, "error", "$.owner_approval.scope", "Owner approval scope must be production.")

    errors, _ = _count_issues(issues)
    return _result(
        errors == 0,
        issues,
        {
            "external_evidence_version": manifest.get("external_evidence_version"),
            "required_artifacts": list(REQUIRED_EXTERNAL_EVIDENCE_ARTIFACTS),
            "connector_count": len(connector_manifests),
            "required_connectors": sorted(required_connectors),
        },
    )


def validate_certification_policy(policy):
    issues = []
    if not isinstance(policy, dict):
        return _result(
            False,
            [{"level": "error", "path": "$", "message": "Production certification policy must be a JSON object."}],
        )

    if policy.get("production_certification_version") != PRODUCTION_CERTIFICATION_VERSION:
        _add_issue(
            issues,
            "error",
            "$.production_certification_version",
            f"production_certification_version must be {PRODUCTION_CERTIFICATION_VERSION}.",
        )
    if not _has_text(policy.get("policy_name")):
        _add_issue(issues, "error", "$.policy_name", "policy_name must be a non-empty string.")
    if not _has_text(policy.get("owner")):
        _add_issue(issues, "error", "$.owner", "owner must be a non-empty string.")

    shadow = _object(policy.get("shadow_mode"))
    duration = shadow.get("minimum_duration_days")
    records = shadow.get("minimum_records")
    if not isinstance(duration, int) or duration < MIN_SHADOW_DURATION_DAYS:
        _add_issue(
            issues,
            "error",
            "$.shadow_mode.minimum_duration_days",
            f"Shadow mode must run for at least {MIN_SHADOW_DURATION_DAYS} days before production certification.",
        )
    if not isinstance(records, int) or records < MIN_SHADOW_RECORDS:
        _add_issue(
            issues,
            "error",
            "$.shadow_mode.minimum_records",
            f"Shadow mode must include at least {MIN_SHADOW_RECORDS} redacted audit records.",
        )

    metrics = _object(policy.get("metrics"))
    required_metrics = set(_list(metrics.get("required")))
    missing_metrics = sorted(REQUIRED_PRODUCTION_METRICS - required_metrics)
    if missing_metrics:
        _add_issue(
            issues,
            "error",
            "$.metrics.required",
            "Production certification metrics are missing: " + ", ".join(missing_metrics),
        )
    if not isinstance(metrics.get("minimum_aix_score_average"), (int, float)):
        _add_issue(issues, "error", "$.metrics.minimum_aix_score_average", "minimum_aix_score_average must be numeric.")
    if not isinstance(metrics.get("maximum_aix_hard_blockers"), int):
        _add_issue(issues, "error", "$.metrics.maximum_aix_hard_blockers", "maximum_aix_hard_blockers must be an integer.")

    human_review = _object(policy.get("human_review"))
    topics = " ".join(str(item).lower() for item in _list(human_review.get("required_for")))
    for topic in sorted(REQUIRED_HUMAN_REVIEW_TOPICS):
        if topic not in topics:
            _add_issue(
                issues,
                "error",
                "$.human_review.required_for",
                f"Human review routing must cover {topic} decisions.",
            )
    if not _list(human_review.get("required_routes")):
        _add_issue(issues, "error", "$.human_review.required_routes", "At least one human-review route is required.")

    connector_evidence = _object(policy.get("connector_evidence"))
    if not _list(connector_evidence.get("required_connectors")):
        _add_issue(issues, "error", "$.connector_evidence.required_connectors", "At least one connector evidence contract is required.")
    for key in ("auth_boundary_required", "freshness_slo_required", "redaction_required", "failure_modes_required"):
        if connector_evidence.get(key) is not True:
            _add_issue(issues, "error", f"$.connector_evidence.{key}", f"{key} must be true for production certification.")

    audit_retention = _object(policy.get("audit_retention"))
    retention_days = audit_retention.get("minimum_days")
    if not isinstance(retention_days, int) or retention_days < MIN_AUDIT_RETENTION_DAYS:
        _add_issue(
            issues,
            "error",
            "$.audit_retention.minimum_days",
            f"Audit retention must be at least {MIN_AUDIT_RETENTION_DAYS} days.",
        )
    for key in ("immutable_required", "redaction_required"):
        if audit_retention.get(key) is not True:
            _add_issue(issues, "error", f"$.audit_retention.{key}", f"{key} must be true.")

    approvals = _object(policy.get("approvals"))
    for key in ("domain_owner_signoff", "security_signoff", "governance_signoff"):
        if approvals.get(key) is not True:
            _add_issue(issues, "error", f"$.approvals.{key}", f"{key} must be true.")

    errors, _ = _count_issues(issues)
    return _result(errors == 0, issues, {"policy": policy})


def _check(name, status, message, details=None):
    return {"name": name, "status": status, "message": message, "details": details or {}}


def _parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _flatten_records(records):
    flattened = []
    for record in records:
        if isinstance(record, dict) and record.get("record_type") == "workflow_batch_check":
            nested = record.get("records")
            if isinstance(nested, list):
                flattened.extend(item for item in nested if isinstance(item, dict))
                continue
        if isinstance(record, dict):
            flattened.append(record)
    return flattened


def _shadow_mode_audit_report(audit_log_path, policy):
    records = agent_api.load_audit_records(audit_log_path)
    validation = agent_api.validate_audit_records(records)
    redaction = agent_api.audit_redaction_report(records)
    flattened = _flatten_records(records)
    shadow_records = [record for record in flattened if record.get("execution_mode") == "shadow"]
    timestamps = [_parse_timestamp(record.get("created_at")) for record in shadow_records]
    timestamps = [item for item in timestamps if item is not None]
    duration_days = 0
    if len(timestamps) >= 2:
        duration_days = (max(timestamps) - min(timestamps)).days
    metrics_export = agent_api.export_audit_metrics(records, audit_log_path=audit_log_path)

    shadow_policy = _object(policy.get("shadow_mode"))
    min_duration = shadow_policy.get("minimum_duration_days", MIN_SHADOW_DURATION_DAYS)
    min_records = shadow_policy.get("minimum_records", MIN_SHADOW_RECORDS)
    required_adapters = set(_list(shadow_policy.get("required_adapter_ids")))
    observed_adapters = {
        record.get("adapter") or record.get("adapter_id")
        for record in shadow_records
        if record.get("adapter") or record.get("adapter_id")
    }
    missing_adapters = sorted(required_adapters - observed_adapters)

    issues = []
    if not validation["valid"]:
        _add_issue(issues, "error", "$.audit_log", "Shadow audit log schema validation failed.")
    if not redaction["valid"]:
        _add_issue(issues, "error", "$.audit_log", "Shadow audit log redaction validation failed.")
    if len(shadow_records) < min_records:
        _add_issue(
            issues,
            "error",
            "$.shadow_mode.minimum_records",
            f"Shadow audit log has {len(shadow_records)} shadow records; {min_records} required.",
        )
    if duration_days < min_duration:
        _add_issue(
            issues,
            "error",
            "$.shadow_mode.minimum_duration_days",
            f"Shadow audit log spans {duration_days} day(s); {min_duration} required.",
        )
    if missing_adapters:
        _add_issue(
            issues,
            "error",
            "$.shadow_mode.required_adapter_ids",
            "Shadow audit log is missing required adapter coverage: " + ", ".join(missing_adapters),
        )

    metrics_policy = _object(policy.get("metrics"))
    aix_report = production.validate_aix_audit_metrics(
        metrics_export,
        min_average_score=metrics_policy.get("minimum_aix_score_average", 0.85),
        min_min_score=metrics_policy.get("minimum_aix_score_min", 0.5),
        max_hard_blockers=metrics_policy.get("maximum_aix_hard_blockers", 0),
        allowed_decisions=metrics_policy.get("allowed_aix_decisions"),
    )
    issues.extend(aix_report.get("issues", []))

    errors, _ = _count_issues(issues)
    return _result(
        errors == 0,
        issues,
        {
            "audit_log": str(audit_log_path),
            "record_count": len(flattened),
            "shadow_record_count": len(shadow_records),
            "duration_days": duration_days,
            "observed_adapters": sorted(observed_adapters),
            "validation": validation,
            "redaction": redaction,
            "metrics": metrics_export,
            "aix_audit": aix_report,
        },
    )


def _metrics_policy_report(certification_policy, observability_policy):
    certification_metrics = set(_list(_object(certification_policy.get("metrics")).get("required")))
    tracked = set(_list(observability_policy.get("tracked_metrics")))
    missing = sorted(certification_metrics - tracked)
    issues = []
    if missing:
        _add_issue(
            issues,
            "error",
            "$.tracked_metrics",
            "Observability policy does not track production certification metrics: " + ", ".join(missing),
        )
    errors, _ = _count_issues(issues)
    return _result(errors == 0, issues, {"required_metrics": sorted(certification_metrics), "tracked_metrics": sorted(tracked)})


def _human_review_report(certification_policy, deployment_manifest, governance_policy):
    required_for = " ".join(str(item).lower() for item in _list(_object(certification_policy.get("human_review")).get("required_for")))
    deployment_review = _object(deployment_manifest.get("human_review"))
    deployment_text = " ".join(str(item).lower() for item in _list(deployment_review.get("required_for")))
    governance_classes = _list(governance_policy.get("escalation_classes"))
    governance_text = " ".join(
        " ".join(str(item.get(key, "")).lower() for key in ("name", "trigger", "route"))
        for item in governance_classes
        if isinstance(item, dict)
    )
    issues = []
    for topic in sorted(REQUIRED_HUMAN_REVIEW_TOPICS):
        if topic not in required_for:
            _add_issue(issues, "error", "$.certification_policy.human_review.required_for", f"Certification policy is missing {topic}.")
        if topic not in deployment_text:
            _add_issue(issues, "error", "$.deployment_manifest.human_review.required_for", f"Deployment human-review routing is missing {topic}.")
        if topic not in governance_text:
            _add_issue(issues, "error", "$.governance_policy.escalation_classes", f"Governance escalation classes are missing {topic}.")
    errors, _ = _count_issues(issues)
    return _result(errors == 0, issues)


def _audit_retention_report(certification_policy, deployment_manifest):
    policy = _object(certification_policy.get("audit_retention"))
    audit = _object(deployment_manifest.get("audit"))
    min_days = policy.get("minimum_days", MIN_AUDIT_RETENTION_DAYS)
    issues = []
    if audit.get("immutable") is not True:
        _add_issue(issues, "error", "$.audit.immutable", "Production audit sink must be immutable or append-only.")
    if audit.get("redaction_required") is not True:
        _add_issue(issues, "error", "$.audit.redaction_required", "Production audit records must require redaction.")
    if not isinstance(audit.get("retention_days"), int) or audit.get("retention_days") < min_days:
        _add_issue(issues, "error", "$.audit.retention_days", f"Audit retention must be at least {min_days} days.")
    errors, _ = _count_issues(issues)
    return _result(errors == 0, issues, {"required_retention_days": min_days, "declared_retention_days": audit.get("retention_days")})


def production_certification_report(
    *,
    certification_policy,
    deployment_manifest=None,
    governance_policy=None,
    evidence_registry=None,
    observability_policy=None,
    audit_log=None,
    external_evidence_manifest=None,
):
    checks = []
    policy_report = validate_certification_policy(certification_policy)
    checks.append(
        _check(
            "certification_policy",
            "pass" if policy_report["valid"] else "fail",
            "Production certification policy is valid." if policy_report["valid"] else "Production certification policy is invalid.",
            policy_report,
        )
    )
    checks.append(
        _check(
            "readiness_boundary",
            "pass",
            "Demo, pilot, and production readiness boundaries are defined.",
            readiness_boundary(),
        )
    )

    loaded_deployment = None
    if deployment_manifest:
        deployment_report = production.validate_deployment_manifest(deployment_manifest)
        loaded_deployment = deployment_manifest
        checks.append(
            _check(
                "deployment_manifest",
                "pass" if deployment_report["production_ready"] else "fail",
                "Deployment manifest satisfies production certification infrastructure gates."
                if deployment_report["production_ready"]
                else "Deployment manifest does not satisfy production certification gates.",
                deployment_report,
            )
        )
    else:
        checks.append(_check("deployment_manifest", "fail", "Production certification requires a deployment manifest."))

    loaded_governance = None
    if governance_policy:
        governance_report = production.validate_governance_policy(governance_policy)
        loaded_governance = governance_policy
        checks.append(
            _check(
                "governance_policy",
                "pass" if governance_report["production_ready"] else "fail",
                "Governance policy satisfies production certification gates."
                if governance_report["production_ready"]
                else "Governance policy does not satisfy production certification gates.",
                governance_report,
            )
        )
    else:
        checks.append(_check("governance_policy", "fail", "Production certification requires a human-governance policy."))

    if observability_policy:
        observability_report = production.validate_observability_policy(observability_policy)
        metrics_report = _metrics_policy_report(certification_policy, observability_policy)
        status = "pass" if observability_report["production_ready"] and metrics_report["valid"] else "fail"
        checks.append(
            _check(
                "required_metrics",
                status,
                "Observability policy tracks all production certification metrics."
                if status == "pass"
                else "Observability policy is missing required production certification metrics.",
                {"observability": observability_report, "metrics": metrics_report},
            )
        )
    else:
        checks.append(_check("required_metrics", "fail", "Production certification requires an observability policy."))

    if evidence_registry:
        registry_report = agent_api.validate_evidence_registry(evidence_registry)
        coverage = evidence_integrations.integration_coverage_report(registry=evidence_registry)
        required_connectors = set(_list(_object(certification_policy.get("connector_evidence")).get("required_connectors")))
        covered_connectors = {
            item.get("integration_id")
            for item in _list(coverage.get("integrations"))
            if isinstance(item, dict) and item.get("registry_covered")
        }
        missing_connectors = sorted(required_connectors - covered_connectors)
        connector_issues = []
        if missing_connectors:
            _add_issue(
                connector_issues,
                "error",
                "$.connector_evidence.required_connectors",
                "Evidence registry is missing required connector coverage: " + ", ".join(missing_connectors),
            )
        status = "pass" if registry_report["production_ready"] and coverage["valid"] and not missing_connectors else "fail"
        checks.append(
            _check(
                "connector_evidence",
                status,
                "Evidence registry covers production connector evidence contracts."
                if status == "pass"
                else "Evidence registry does not cover production connector evidence contracts.",
                {"registry": registry_report, "coverage": coverage, "issues": connector_issues},
            )
        )
    else:
        checks.append(_check("connector_evidence", "fail", "Production certification requires an evidence registry."))

    if loaded_deployment and loaded_governance:
        human_review = _human_review_report(certification_policy, loaded_deployment, loaded_governance)
        checks.append(
            _check(
                "human_review_routing",
                "pass" if human_review["valid"] else "fail",
                "Human-review routing covers high-impact, low-confidence, and irreversible decisions."
                if human_review["valid"]
                else "Human-review routing is incomplete.",
                human_review,
            )
        )
        audit_retention = _audit_retention_report(certification_policy, loaded_deployment)
        checks.append(
            _check(
                "audit_retention",
                "pass" if audit_retention["valid"] else "fail",
                "Audit retention, immutability, and redaction satisfy production certification."
                if audit_retention["valid"]
                else "Audit retention, immutability, or redaction is insufficient.",
                audit_retention,
            )
        )
    else:
        checks.append(_check("human_review_routing", "fail", "Human-review routing requires deployment and governance inputs."))
        checks.append(_check("audit_retention", "fail", "Audit retention requires deployment manifest input."))

    if audit_log:
        shadow_report = _shadow_mode_audit_report(audit_log, certification_policy)
        checks.append(
            _check(
                "shadow_mode_evidence",
                "pass" if shadow_report["valid"] else "fail",
                "Shadow-mode audit evidence satisfies production certification."
                if shadow_report["valid"]
                else "Shadow-mode audit evidence is insufficient for production certification.",
                shadow_report,
            )
        )
    else:
        checks.append(_check("shadow_mode_evidence", "fail", "Production certification requires a redacted shadow-mode audit log."))

    repo_failed = [item for item in checks if item["status"] == "fail"]
    repo_warnings = [item for item in checks if item["status"] == "warn"]
    repo_local_ready = not repo_failed and not repo_warnings

    if external_evidence_manifest:
        external_report = validate_external_evidence_manifest(external_evidence_manifest, certification_policy)
        checks.append(
            _check(
                "external_production_evidence",
                "pass" if external_report["valid"] else "fail",
                "External production evidence is explicit and satisfies production-claim prerequisites."
                if external_report["valid"]
                else "External production evidence is missing or incomplete; production claims are not allowed.",
                external_report,
            )
        )
    else:
        checks.append(
            _check(
                "external_production_evidence",
                "fail",
                "Production claims require explicit external evidence: connector manifests, shadow-mode logs, audit retention policy, escalation policy, and owner approval.",
                {"required_artifacts": list(REQUIRED_EXTERNAL_EVIDENCE_ARTIFACTS)},
            )
        )

    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    deployment_ready = repo_local_ready and not failed and not warnings
    readiness_level = (
        "deployment_ready"
        if deployment_ready
        else "external_evidence_required"
        if repo_local_ready
        else "repo_local_not_ready"
    )
    return {
        "production_certification_version": PRODUCTION_CERTIFICATION_VERSION,
        "production_positioning": CONSERVATIVE_PRODUCTION_POSITIONING,
        "certification_scope": BOUNDARY_CHECKER_LINE,
        "valid": not failed,
        "production_ready": deployment_ready,
        "repo_local_ready": repo_local_ready,
        "deployment_ready": deployment_ready,
        "production_certified": False,
        "production_claim_allowed": deployment_ready,
        "summary": {
            "status": "pass" if deployment_ready else "fail" if failed else "warn",
            "readiness_level": readiness_level,
            "checks": len(checks),
            "failures": len(failed),
            "warnings": len(warnings),
            "repo_local_failures": len(repo_failed),
            "repo_local_warnings": len(repo_warnings),
        },
        "readiness_boundary": readiness_boundary(),
        "public_readiness_matrix": certification_program_matrix(),
        "checks": checks,
    }


def production_certification_report_from_paths(
    *,
    certification_policy_path,
    deployment_manifest_path=None,
    governance_policy_path=None,
    evidence_registry_path=None,
    observability_policy_path=None,
    audit_log_path=None,
    external_evidence_path=None,
):
    certification_policy = agent_api.load_json_file(pathlib.Path(certification_policy_path))
    deployment_manifest = agent_api.load_json_file(pathlib.Path(deployment_manifest_path)) if deployment_manifest_path else None
    governance_policy = agent_api.load_json_file(pathlib.Path(governance_policy_path)) if governance_policy_path else None
    evidence_registry = agent_api.load_evidence_registry(pathlib.Path(evidence_registry_path)) if evidence_registry_path else None
    observability_policy = agent_api.load_json_file(pathlib.Path(observability_policy_path)) if observability_policy_path else None
    external_evidence_manifest = agent_api.load_json_file(pathlib.Path(external_evidence_path)) if external_evidence_path else None
    return production_certification_report(
        certification_policy=certification_policy,
        deployment_manifest=deployment_manifest,
        governance_policy=governance_policy,
        evidence_registry=evidence_registry,
        observability_policy=observability_policy,
        audit_log=pathlib.Path(audit_log_path) if audit_log_path else None,
        external_evidence_manifest=external_evidence_manifest,
    )
