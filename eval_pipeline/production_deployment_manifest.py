"""Production deployment manifest bound to a verified AANA MI release bundle."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH
from eval_pipeline.live_connector_readiness import DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH
from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_bundle_verification import DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH


PRODUCTION_DEPLOYMENT_MANIFEST_VERSION = "0.1"
PRODUCTION_DEPLOYMENT_MANIFEST_TYPE = "aana_mi_production_deployment_manifest"
DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "production_deployment_manifest.json"
DEFAULT_RELEASE_MANIFEST_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_manifest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _optional_json(path: pathlib.Path) -> dict[str, Any]:
    return _load_json(path) if path.exists() else {}


def _artifact_ref(path: pathlib.Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": _sha256_file(path) if path.exists() else None,
        "bytes": path.stat().st_size if path.exists() else None,
    }


def production_deployment_manifest(
    *,
    release_manifest_path: str | pathlib.Path = DEFAULT_RELEASE_MANIFEST_PATH,
    verification_path: str | pathlib.Path = DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH,
    human_signoff_path: str | pathlib.Path = DEFAULT_HUMAN_SIGNOFF_PATH,
    live_connector_plan_path: str | pathlib.Path = DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
    rollback_owner: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a production deployment manifest referencing a verified MI bundle."""

    release_path = pathlib.Path(release_manifest_path)
    verification_file = pathlib.Path(verification_path)
    signoff_file = pathlib.Path(human_signoff_path)
    connector_file = pathlib.Path(live_connector_plan_path)
    release_manifest = _load_json(release_path)
    verification = _load_json(verification_file)
    signoff = _optional_json(signoff_file)
    connector_plan = _optional_json(connector_file)
    signoff_decision = signoff.get("decision", "missing")
    verification_status = verification.get("status")
    live_enabled_count = None
    if isinstance(connector_plan.get("summary"), dict):
        live_enabled_count = connector_plan["summary"].get("live_execution_enabled_count")

    deployment_authorized = (
        verification_status == "pass"
        and release_manifest.get("rc_status") == "pass"
        and release_manifest.get("readiness_status") == "ready"
        and release_manifest.get("unresolved_blocker_count") == 0
        and signoff_decision == "approved"
        and live_enabled_count == 0
    )

    return {
        "production_deployment_manifest_version": PRODUCTION_DEPLOYMENT_MANIFEST_VERSION,
        "manifest_type": PRODUCTION_DEPLOYMENT_MANIFEST_TYPE,
        "created_at": created_at or _utc_now(),
        "deployment_status": "authorized" if deployment_authorized else "blocked",
        "deployment_authorized": deployment_authorized,
        "blockers": []
        if deployment_authorized
        else [
            blocker
            for blocker, active in (
                ("release_bundle_verification_not_pass", verification_status != "pass"),
                ("release_candidate_not_pass", release_manifest.get("rc_status") != "pass"),
                ("readiness_not_ready", release_manifest.get("readiness_status") != "ready"),
                ("unresolved_blockers_present", release_manifest.get("unresolved_blocker_count") != 0),
                ("human_signoff_not_approved", signoff_decision != "approved"),
                ("live_connector_plan_missing_or_live_enabled", live_enabled_count != 0),
            )
            if active
        ],
        "verified_mi_release_bundle": {
            "release_manifest": _artifact_ref(release_path),
            "release_bundle_verification": _artifact_ref(verification_file),
            "verification_status": verification_status,
            "rc_status": release_manifest.get("rc_status"),
            "readiness_status": release_manifest.get("readiness_status"),
            "global_aix": release_manifest.get("global_aix") if isinstance(release_manifest.get("global_aix"), dict) else {},
            "unresolved_blocker_count": release_manifest.get("unresolved_blocker_count"),
        },
        "environment_assumptions": {
            "target_environment": "production",
            "deployment_mode": "guarded_live_after_approval",
            "network_boundary": "external_connectors_disabled_until_connector_specific_enablement",
            "runtime_entrypoint": "aana-mi-release plus production pre-execution hooks",
            "required_python": ">=3.10",
            "required_controls": [
                "verified_release_bundle",
                "approved_human_signoff",
                "immutable_audit_storage",
                "live_connector_readiness_review",
                "secrets_in_environment_or_vault_only",
                "rollback_owner_available",
            ],
        },
        "secrets_policy": {
            "storage": "environment_or_managed_secret_vault_only",
            "plaintext_files_allowed": False,
            "secrets_in_logs_allowed": False,
            "secrets_in_release_bundle_allowed": False,
            "rotation_required": True,
            "scan_required_before_deploy": True,
            "required_secret_names": ["AANA_BRIDGE_TOKEN"],
        },
        "audit_policy": {
            "mode": "redacted_decision_metadata_only",
            "raw_prompts_allowed": False,
            "raw_evidence_allowed": False,
            "raw_private_content_allowed": False,
            "sha256_manifest_required": True,
            "append_only_storage_required": True,
            "retention_owner": "pending-security-owner",
            "artifact_paths": {
                "audit_jsonl": release_manifest.get("artifacts", {}).get("audit_jsonl", {}).get("bundle_path")
                if isinstance(release_manifest.get("artifacts"), dict)
                else None,
                "audit_manifest": release_manifest.get("artifacts", {}).get("audit_manifest", {}).get("bundle_path")
                if isinstance(release_manifest.get("artifacts"), dict)
                else None,
            },
        },
        "rollback": {
            "owner": rollback_owner
            if isinstance(rollback_owner, dict)
            else {
                "id": "pending-release-owner",
                "name": "Pending release owner",
                "role": "release_manager",
            },
            "rollback_required_before_live_enablement": True,
            "default_strategy": "disable_live_connectors_and_restore_previous_verified_bundle",
            "decision_routes": {
                "bundle_verification_failure": "block",
                "audit_integrity_failure": "block",
                "global_aix_regression": "defer",
                "connector_failure": "rollback_or_defer",
            },
        },
        "external_control_refs": {
            "human_signoff": _artifact_ref(signoff_file),
            "live_connector_readiness_plan": _artifact_ref(connector_file),
        },
    }


def validate_production_deployment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate deployment manifest shape and release-bundle binding."""

    issues: list[dict[str, str]] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Manifest must be an object."}]}
    if manifest.get("production_deployment_manifest_version") != PRODUCTION_DEPLOYMENT_MANIFEST_VERSION:
        issues.append({"path": "$.production_deployment_manifest_version", "message": f"Must be {PRODUCTION_DEPLOYMENT_MANIFEST_VERSION}."})
    if manifest.get("manifest_type") != PRODUCTION_DEPLOYMENT_MANIFEST_TYPE:
        issues.append({"path": "$.manifest_type", "message": f"Must be {PRODUCTION_DEPLOYMENT_MANIFEST_TYPE}."})

    bundle = manifest.get("verified_mi_release_bundle") if isinstance(manifest.get("verified_mi_release_bundle"), dict) else {}
    if bundle.get("verification_status") != "pass":
        issues.append({"path": "$.verified_mi_release_bundle.verification_status", "message": "Release bundle verification must pass."})
    if bundle.get("rc_status") != "pass":
        issues.append({"path": "$.verified_mi_release_bundle.rc_status", "message": "Release candidate status must pass."})
    if bundle.get("readiness_status") != "ready":
        issues.append({"path": "$.verified_mi_release_bundle.readiness_status", "message": "Readiness status must be ready."})
    if bundle.get("unresolved_blocker_count") != 0:
        issues.append({"path": "$.verified_mi_release_bundle.unresolved_blocker_count", "message": "Unresolved blocker count must be zero."})
    global_aix = bundle.get("global_aix") if isinstance(bundle.get("global_aix"), dict) else {}
    score = global_aix.get("score")
    threshold = global_aix.get("accept_threshold", 0)
    if not isinstance(score, (int, float)) or not isinstance(threshold, (int, float)) or float(score) < float(threshold):
        issues.append({"path": "$.verified_mi_release_bundle.global_aix.score", "message": "Global AIx must meet its accept threshold."})

    for field in ("environment_assumptions", "secrets_policy", "audit_policy", "rollback"):
        if not isinstance(manifest.get(field), dict):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an object."})

    secrets = manifest.get("secrets_policy") if isinstance(manifest.get("secrets_policy"), dict) else {}
    if secrets.get("plaintext_files_allowed") is not False:
        issues.append({"path": "$.secrets_policy.plaintext_files_allowed", "message": "Plaintext secret files must not be allowed."})
    if secrets.get("secrets_in_logs_allowed") is not False or secrets.get("secrets_in_release_bundle_allowed") is not False:
        issues.append({"path": "$.secrets_policy", "message": "Secrets must not be allowed in logs or release bundles."})

    audit = manifest.get("audit_policy") if isinstance(manifest.get("audit_policy"), dict) else {}
    if audit.get("mode") != "redacted_decision_metadata_only":
        issues.append({"path": "$.audit_policy.mode", "message": "Audit mode must be redacted decision metadata only."})
    for field in ("raw_prompts_allowed", "raw_evidence_allowed", "raw_private_content_allowed"):
        if audit.get(field) is not False:
            issues.append({"path": f"$.audit_policy.{field}", "message": "Raw content must not be allowed in production MI audit."})
    if audit.get("append_only_storage_required") is not True:
        issues.append({"path": "$.audit_policy.append_only_storage_required", "message": "Append-only audit storage is required for production."})

    rollback = manifest.get("rollback") if isinstance(manifest.get("rollback"), dict) else {}
    owner = rollback.get("owner") if isinstance(rollback.get("owner"), dict) else {}
    for field in ("id", "name", "role"):
        if not isinstance(owner.get(field), str) or not owner.get(field).strip():
            issues.append({"path": f"$.rollback.owner.{field}", "message": "Rollback owner field must be a non-empty string."})
    if rollback.get("rollback_required_before_live_enablement") is not True:
        issues.append({"path": "$.rollback.rollback_required_before_live_enablement", "message": "Rollback must be required before live enablement."})

    external = manifest.get("external_control_refs") if isinstance(manifest.get("external_control_refs"), dict) else {}
    for name in ("human_signoff", "live_connector_readiness_plan"):
        ref = external.get(name) if isinstance(external.get(name), dict) else {}
        if ref.get("exists") is not True:
            issues.append({"path": f"$.external_control_refs.{name}", "message": f"{name} artifact must exist."})

    if manifest.get("deployment_authorized") is True and manifest.get("blockers"):
        issues.append({"path": "$.deployment_authorized", "message": "Authorized deployments must not have blockers."})
    if manifest.get("deployment_authorized") is False and not isinstance(manifest.get("blockers"), list):
        issues.append({"path": "$.blockers", "message": "Blocked deployments must list blockers."})

    return {"valid": not issues, "issues": issues}


def write_production_deployment_manifest(
    path: str | pathlib.Path = DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    *,
    release_manifest_path: str | pathlib.Path = DEFAULT_RELEASE_MANIFEST_PATH,
    verification_path: str | pathlib.Path = DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH,
    human_signoff_path: str | pathlib.Path = DEFAULT_HUMAN_SIGNOFF_PATH,
    live_connector_plan_path: str | pathlib.Path = DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
    rollback_owner: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the production deployment manifest artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = production_deployment_manifest(
        release_manifest_path=release_manifest_path,
        verification_path=verification_path,
        human_signoff_path=human_signoff_path,
        live_connector_plan_path=live_connector_plan_path,
        rollback_owner=rollback_owner,
    )
    validation = validate_production_deployment_manifest(manifest)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"manifest": manifest, "validation": validation, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH",
    "DEFAULT_RELEASE_MANIFEST_PATH",
    "PRODUCTION_DEPLOYMENT_MANIFEST_TYPE",
    "PRODUCTION_DEPLOYMENT_MANIFEST_VERSION",
    "production_deployment_manifest",
    "validate_production_deployment_manifest",
    "write_production_deployment_manifest",
]
