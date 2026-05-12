"""MedPerf healthcare AIx profile for regulated medical evaluation audits."""

from __future__ import annotations

import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
MEDPERF_AIX_PROFILE_VERSION = "0.1"
MEDPERF_AIX_PROFILE_TYPE = "aana_medperf_aix_profile"
DEFAULT_MEDPERF_AIX_PROFILE_PATH = ROOT / "examples" / "medperf_aix_profile_healthcare.json"
DEFAULT_MEDPERF_AIX_REPORT_PATH = ROOT / "eval_outputs" / "medperf" / "medperf-aix-healthcare-section.json"
MEDPERF_CLAIM_BOUNDARY = (
    "Healthcare evaluation profile only; pilot readiness is not production certification, "
    "clinical deployment approval, medical device clearance, or clinical advice."
)
REQUIRED_HEALTHCARE_CONTEXT_FIELDS = (
    "site",
    "dataset",
    "model",
    "clinical_task",
    "evaluation_owner",
    "privacy_controls",
    "clinical_owner_signoff",
    "site_approval",
)
STRICT_COMPONENT_WEIGHTS = {"P": 0.2, "B": 0.35, "C": 0.3, "F": 0.15}


def _issue(level: str, path: str, message: str, hard_blocker: str | None = None) -> dict[str, str]:
    issue = {"level": level, "path": path, "message": message}
    if hard_blocker:
        issue["hard_blocker"] = hard_blocker
    return issue


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _section(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _approved(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"approved", "exempt", "not_applicable_synthetic_fixture"}


def default_medperf_aix_profile() -> dict[str, Any]:
    """Return the default MedPerf healthcare AIx profile."""

    return {
        "medperf_aix_profile_version": MEDPERF_AIX_PROFILE_VERSION,
        "profile_type": MEDPERF_AIX_PROFILE_TYPE,
        "profile_id": "medperf_healthcare_strict_v1",
        "product": "AANA AIx Audit",
        "mlcommons_surface": "medperf",
        "risk_tier": "strict",
        "deployment_context": "federated_medical_ai_evaluation",
        "claim_boundary": MEDPERF_CLAIM_BOUNDARY,
        "required_fields": list(REQUIRED_HEALTHCARE_CONTEXT_FIELDS),
        "evaluation_context": {
            "site": {
                "site_id": "synthetic-hospital-site",
                "site_name": "Synthetic Hospital Site",
                "jurisdiction": "US",
            },
            "site_approval": {
                "approval_status": "approved",
                "approval_reference": "synthetic-site-approval-2026-05",
                "approved_by": "Site Evaluation Owner",
            },
            "dataset": {
                "dataset_id": "synthetic-radiology-demo",
                "provenance_source": "examples/croissant_metadata_sample.json",
                "contains_phi": False,
                "data_use_agreement": "synthetic-data-only",
            },
            "model": {
                "model_id": "example-medical-triage-model",
                "version": "0.1",
                "model_card": "synthetic model card metadata",
            },
            "clinical_task": {
                "task_id": "triage_assist",
                "clinical_domain": "radiology",
                "intended_use": "Assist evaluation of synthetic triage workflow outputs during a federated benchmark pilot.",
                "unsupported_uses": [
                    "autonomous diagnosis",
                    "treatment selection without clinician review",
                    "emergency-care routing without human oversight",
                ],
                "unsupported_medical_claims_detected": False,
            },
            "evaluation_owner": {
                "name": "Clinical Evaluation Owner",
                "role": "medical_director",
                "contact": "redacted",
            },
            "privacy_controls": {
                "privacy_boundary": "synthetic_or_deidentified_only",
                "phi_allowed": False,
                "de_identification_required": True,
                "raw_records_in_audit_allowed": False,
                "redacted_audit_required": True,
            },
            "irb_ethics": {
                "required": False,
                "status": "not_applicable_synthetic_fixture",
                "reference": "synthetic-demo",
            },
            "clinical_owner_signoff": {
                "status": "approved",
                "owner": "Clinical Evaluation Owner",
                "signed_at": "2026-05-12T00:00:00Z",
            },
        },
        "hard_blocker_rules": [
            {
                "id": "missing_site_approval",
                "description": "The evaluation site must have an explicit approval marker before healthcare audit readiness.",
            },
            {
                "id": "missing_privacy_boundary",
                "description": "The profile must declare privacy controls, PHI boundary, and redacted audit handling.",
            },
            {
                "id": "unsupported_medical_claim",
                "description": "Unsupported diagnosis, treatment, or autonomous clinical claims block readiness.",
            },
            {
                "id": "missing_clinical_owner_signoff",
                "description": "A clinical owner must sign off before healthcare evaluation readiness.",
            },
        ],
        "aix": {
            "risk_tier": "strict",
            "beta": 2.0,
            "component_weights": STRICT_COMPONENT_WEIGHTS,
            "thresholds": {
                "accept_min": 0.95,
                "revise_min": 0.9,
                "defer_below": 0.9,
            },
        },
        "reporting": {
            "healthcare_section_required": True,
            "include_site_summary": True,
            "include_privacy_boundary": True,
            "include_clinical_owner_signoff": True,
            "include_irb_ethics_marker": True,
        },
        "limitations": [
            "This profile supports healthcare evaluation audit readiness, not clinical deployment approval.",
            "Production use still requires site governance, security review, human-review operations, and measured shadow-mode evidence.",
            "Medical claims must remain inside the declared clinical task and unsupported-use boundaries.",
        ],
    }


def load_medperf_aix_profile(path: str | pathlib.Path = DEFAULT_MEDPERF_AIX_PROFILE_PATH) -> dict[str, Any]:
    return _load_json(path)


def validate_medperf_aix_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate MedPerf healthcare audit profile structure and hard blockers."""

    issues: list[dict[str, str]] = []
    hard_blockers: list[str] = []
    if not isinstance(profile, dict):
        return {
            "valid": False,
            "healthcare_evaluation_ready": False,
            "go_live_ready": False,
            "risk_tier": None,
            "hard_blockers": [],
            "errors": 1,
            "warnings": 0,
            "issues": [_issue("error", "$", "MedPerf AIx profile must be a JSON object.")],
            "summary": {},
        }

    if profile.get("medperf_aix_profile_version") != MEDPERF_AIX_PROFILE_VERSION:
        issues.append(_issue("error", "medperf_aix_profile_version", f"Must be {MEDPERF_AIX_PROFILE_VERSION}."))
    if profile.get("profile_type") != MEDPERF_AIX_PROFILE_TYPE:
        issues.append(_issue("error", "profile_type", f"Must be {MEDPERF_AIX_PROFILE_TYPE}."))
    if profile.get("mlcommons_surface") != "medperf":
        issues.append(_issue("error", "mlcommons_surface", "MedPerf AIx profile must target mlcommons_surface=medperf."))
    if profile.get("risk_tier") != "strict":
        issues.append(_issue("error", "risk_tier", "Healthcare MedPerf audits must use risk_tier=strict."))
    claim_boundary = str(profile.get("claim_boundary", "")).lower()
    if "not production certification" not in claim_boundary or "clinical deployment" not in claim_boundary:
        issues.append(
            _issue(
                "error",
                "claim_boundary",
                "Claim boundary must state this is not production certification or clinical deployment approval.",
            )
        )

    required_fields = profile.get("required_fields")
    if not isinstance(required_fields, list):
        issues.append(_issue("error", "required_fields", "Required fields must be listed."))
    else:
        missing_required = sorted(set(REQUIRED_HEALTHCARE_CONTEXT_FIELDS) - {str(item) for item in required_fields})
        if missing_required:
            issues.append(_issue("error", "required_fields", "Missing required healthcare fields: " + ", ".join(missing_required)))

    context = _section(profile.get("evaluation_context"))
    for field in REQUIRED_HEALTHCARE_CONTEXT_FIELDS:
        if not _section(context.get(field)):
            blocker = None
            if field == "site_approval":
                blocker = "missing_site_approval"
            elif field == "privacy_controls":
                blocker = "missing_privacy_boundary"
            elif field == "clinical_owner_signoff":
                blocker = "missing_clinical_owner_signoff"
            issues.append(_issue("error", f"evaluation_context.{field}", "Required healthcare evaluation context is missing.", blocker))
            if blocker:
                hard_blockers.append(blocker)

    site = _section(context.get("site"))
    if not _non_empty_text(site.get("site_id")):
        issues.append(_issue("error", "evaluation_context.site.site_id", "Site identifier is required."))

    site_approval = _section(context.get("site_approval"))
    if site_approval.get("approval_status") != "approved" or not _non_empty_text(site_approval.get("approval_reference")):
        issues.append(
            _issue(
                "error",
                "evaluation_context.site_approval",
                "Site approval must be approved and include an approval reference.",
                "missing_site_approval",
            )
        )
        hard_blockers.append("missing_site_approval")

    dataset = _section(context.get("dataset"))
    for key in ("dataset_id", "provenance_source", "data_use_agreement"):
        if not _non_empty_text(dataset.get(key)):
            issues.append(_issue("error", f"evaluation_context.dataset.{key}", "Dataset provenance and use-boundary metadata is required."))
    if dataset.get("contains_phi") is True:
        issues.append(_issue("warning", "evaluation_context.dataset.contains_phi", "PHI requires additional customer privacy controls and legal review."))

    model = _section(context.get("model"))
    for key in ("model_id", "version"):
        if not _non_empty_text(model.get(key)):
            issues.append(_issue("error", f"evaluation_context.model.{key}", "Model identity and version are required."))

    clinical_task = _section(context.get("clinical_task"))
    for key in ("task_id", "intended_use"):
        if not _non_empty_text(clinical_task.get(key)):
            issues.append(_issue("error", f"evaluation_context.clinical_task.{key}", "Clinical task and intended use are required."))
    if clinical_task.get("unsupported_medical_claims_detected") is True:
        issues.append(
            _issue(
                "error",
                "evaluation_context.clinical_task.unsupported_medical_claims_detected",
                "Unsupported medical claims block healthcare audit readiness.",
                "unsupported_medical_claim",
            )
        )
        hard_blockers.append("unsupported_medical_claim")
    unsupported_uses = clinical_task.get("unsupported_uses")
    if not isinstance(unsupported_uses, list) or not unsupported_uses:
        issues.append(_issue("warning", "evaluation_context.clinical_task.unsupported_uses", "Unsupported clinical uses should be declared."))

    owner = _section(context.get("evaluation_owner"))
    for key in ("name", "role"):
        if not _non_empty_text(owner.get(key)):
            issues.append(_issue("error", f"evaluation_context.evaluation_owner.{key}", "Evaluation owner name and role are required."))

    privacy = _section(context.get("privacy_controls"))
    privacy_missing = False
    if not _non_empty_text(privacy.get("privacy_boundary")):
        privacy_missing = True
        issues.append(_issue("error", "evaluation_context.privacy_controls.privacy_boundary", "Privacy boundary is required.", "missing_privacy_boundary"))
    if privacy.get("raw_records_in_audit_allowed") is not False:
        privacy_missing = True
        issues.append(_issue("error", "evaluation_context.privacy_controls.raw_records_in_audit_allowed", "Raw medical records must not be stored in audit artifacts.", "missing_privacy_boundary"))
    if privacy.get("de_identification_required") is not True:
        privacy_missing = True
        issues.append(_issue("error", "evaluation_context.privacy_controls.de_identification_required", "De-identification must be required.", "missing_privacy_boundary"))
    if privacy_missing:
        hard_blockers.append("missing_privacy_boundary")

    irb = _section(context.get("irb_ethics"))
    if irb.get("required") is True and (not _approved(irb.get("status")) or not _non_empty_text(irb.get("reference"))):
        issues.append(_issue("error", "evaluation_context.irb_ethics", "Required IRB/ethics marker must be approved or exempt with a reference."))

    signoff = _section(context.get("clinical_owner_signoff"))
    if signoff.get("status") != "approved" or not _non_empty_text(signoff.get("owner")):
        issues.append(
            _issue(
                "error",
                "evaluation_context.clinical_owner_signoff",
                "Clinical owner signoff must be approved and identify the owner.",
                "missing_clinical_owner_signoff",
            )
        )
        hard_blockers.append("missing_clinical_owner_signoff")

    aix = _section(profile.get("aix"))
    if aix.get("risk_tier") != "strict":
        issues.append(_issue("error", "aix.risk_tier", "AIx tuning must use strict risk tier."))
    if not isinstance(aix.get("beta"), (int, float)) or aix.get("beta") < 2.0:
        issues.append(_issue("error", "aix.beta", "Healthcare strict profile requires beta >= 2.0."))
    weights = _section(aix.get("component_weights"))
    if set(weights) != set(STRICT_COMPONENT_WEIGHTS):
        issues.append(_issue("error", "aix.component_weights", "Component weights must include exactly P, B, C, and F."))
    elif abs(sum(float(value) for value in weights.values()) - 1.0) > 0.001:
        issues.append(_issue("error", "aix.component_weights", "Component weights must sum to 1.0."))
    thresholds = _section(aix.get("thresholds"))
    if thresholds.get("accept_min", 0) < 0.95:
        issues.append(_issue("error", "aix.thresholds.accept_min", "Healthcare strict accept threshold must be at least 0.95."))

    hard_blockers = sorted(set(hard_blockers))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "healthcare_evaluation_ready": errors == 0 and not hard_blockers,
        "go_live_ready": False,
        "risk_tier": profile.get("risk_tier"),
        "hard_blockers": hard_blockers,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "summary": {
            "profile_id": profile.get("profile_id"),
            "mlcommons_surface": profile.get("mlcommons_surface"),
            "deployment_context": profile.get("deployment_context"),
            "site_id": site.get("site_id"),
            "dataset_id": dataset.get("dataset_id"),
            "model_id": model.get("model_id"),
            "clinical_task": clinical_task.get("task_id"),
        },
    }


def build_medperf_aix_report_section(profile: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the healthcare-specific AIx Report section for a MedPerf profile."""

    validation = validation or validate_medperf_aix_profile(profile)
    context = _section(profile.get("evaluation_context"))
    recommendation = "healthcare_evaluation_ready_with_controls" if validation.get("healthcare_evaluation_ready") else "not_healthcare_evaluation_ready"
    return {
        "section_type": "aana_medperf_healthcare_aix_section",
        "section_version": MEDPERF_AIX_PROFILE_VERSION,
        "mlcommons_surface": "medperf",
        "risk_tier": "strict",
        "deployment_recommendation": recommendation,
        "healthcare_evaluation_ready": bool(validation.get("healthcare_evaluation_ready")),
        "go_live_ready": False,
        "claim_boundary": profile.get("claim_boundary", MEDPERF_CLAIM_BOUNDARY),
        "site": {
            "site_id": _section(context.get("site")).get("site_id"),
            "site_name": _section(context.get("site")).get("site_name"),
            "approval_status": _section(context.get("site_approval")).get("approval_status"),
            "approval_reference": _section(context.get("site_approval")).get("approval_reference"),
        },
        "dataset": {
            "dataset_id": _section(context.get("dataset")).get("dataset_id"),
            "provenance_source": _section(context.get("dataset")).get("provenance_source"),
            "contains_phi": _section(context.get("dataset")).get("contains_phi"),
            "data_use_agreement": _section(context.get("dataset")).get("data_use_agreement"),
        },
        "model": {
            "model_id": _section(context.get("model")).get("model_id"),
            "version": _section(context.get("model")).get("version"),
        },
        "clinical_task": {
            "task_id": _section(context.get("clinical_task")).get("task_id"),
            "clinical_domain": _section(context.get("clinical_task")).get("clinical_domain"),
            "intended_use": _section(context.get("clinical_task")).get("intended_use"),
            "unsupported_uses": _section(context.get("clinical_task")).get("unsupported_uses", []),
        },
        "evaluation_owner": {
            "name": _section(context.get("evaluation_owner")).get("name"),
            "role": _section(context.get("evaluation_owner")).get("role"),
            "contact": _section(context.get("evaluation_owner")).get("contact"),
        },
        "privacy_controls": {
            "privacy_boundary": _section(context.get("privacy_controls")).get("privacy_boundary"),
            "phi_allowed": _section(context.get("privacy_controls")).get("phi_allowed"),
            "de_identification_required": _section(context.get("privacy_controls")).get("de_identification_required"),
            "raw_records_in_audit_allowed": _section(context.get("privacy_controls")).get("raw_records_in_audit_allowed"),
            "redacted_audit_required": _section(context.get("privacy_controls")).get("redacted_audit_required"),
        },
        "irb_ethics": context.get("irb_ethics", {}),
        "clinical_owner_signoff": {
            "status": _section(context.get("clinical_owner_signoff")).get("status"),
            "owner": _section(context.get("clinical_owner_signoff")).get("owner"),
            "signed_at": _section(context.get("clinical_owner_signoff")).get("signed_at"),
        },
        "aix_tuning": profile.get("aix", {}),
        "hard_blockers": validation.get("hard_blockers", []),
        "issues": validation.get("issues", []),
        "limitations": profile.get("limitations", []),
    }


def write_medperf_aix_profile(path: str | pathlib.Path = DEFAULT_MEDPERF_AIX_PROFILE_PATH) -> dict[str, Any]:
    profile = default_medperf_aix_profile()
    validation = validate_medperf_aix_profile(profile)
    _write_json(path, profile)
    return {"path": str(path), "profile": profile, "validation": validation}


def write_medperf_aix_report_section(
    profile_path: str | pathlib.Path = DEFAULT_MEDPERF_AIX_PROFILE_PATH,
    report_path: str | pathlib.Path = DEFAULT_MEDPERF_AIX_REPORT_PATH,
) -> dict[str, Any]:
    profile = load_medperf_aix_profile(profile_path)
    validation = validate_medperf_aix_profile(profile)
    section = build_medperf_aix_report_section(profile, validation)
    report = {"profile": profile, "validation": validation, "healthcare_aix_report_section": section}
    _write_json(report_path, report)
    return {"path": str(report_path), **report}


__all__ = [
    "DEFAULT_MEDPERF_AIX_PROFILE_PATH",
    "DEFAULT_MEDPERF_AIX_REPORT_PATH",
    "MEDPERF_AIX_PROFILE_TYPE",
    "MEDPERF_AIX_PROFILE_VERSION",
    "MEDPERF_CLAIM_BOUNDARY",
    "REQUIRED_HEALTHCARE_CONTEXT_FIELDS",
    "build_medperf_aix_report_section",
    "default_medperf_aix_profile",
    "load_medperf_aix_profile",
    "validate_medperf_aix_profile",
    "write_medperf_aix_profile",
    "write_medperf_aix_report_section",
]
