"""Bundle-level certification entrypoint for AANA product bundles."""

from __future__ import annotations

import pathlib
from typing import Any

from aana.adapter_layout import validate_adapter_layout
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, canonicalize_bundle_id, load_bundle
from eval_pipeline import civic_family, enterprise_family, personal_family


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "examples" / "evidence_registry.json"
DEFAULT_MOCK_FIXTURES = ROOT / "examples" / "evidence_mock_connector_fixtures.json"

CERTIFICATION_POLICY_BY_BUNDLE = {
    "enterprise": ROOT / "examples" / "enterprise_certification_policy.json",
    "enterprise_ops_pilot": ROOT / "examples" / "enterprise_certification_policy.json",
    "personal_productivity": ROOT / "examples" / "personal_certification_policy.json",
    "government_civic": ROOT / "examples" / "civic_certification_policy.json",
}

REQUIRED_BUNDLE_FIELDS = (
    "core_adapter_ids",
    "required_evidence_connectors",
    "human_review_required_for",
    "minimum_validation",
)


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _manifest_certification(bundle_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for field in REQUIRED_BUNDLE_FIELDS:
        value = manifest.get(field)
        if field == "minimum_validation":
            valid = isinstance(value, dict) and bool(value)
        else:
            valid = _nonempty_list(value)
        checks.append(
            {
                "id": f"bundle_declares_{field}",
                "status": "pass" if valid else "fail",
                "message": f"Bundle manifest declares non-empty {field}."
                if valid
                else f"Bundle manifest must declare non-empty {field}.",
                "details": {"field": field, "value_count": len(value) if isinstance(value, list) else None},
            }
        )

    minimum_validation = manifest.get("minimum_validation") if isinstance(manifest.get("minimum_validation"), dict) else {}
    required_families = set(minimum_validation.get("required_adapter_families", []))
    adapter_families = set(manifest.get("adapter_families", []))
    coverage = minimum_validation.get("heldout_validation_coverage", [])
    covered_families = {
        item.get("adapter_family")
        for item in coverage
        if isinstance(item, dict) and item.get("adapter_family")
    }
    checks.extend(
        [
            {
                "id": "minimum_validation_matches_adapter_families",
                "status": "pass" if required_families == adapter_families else "fail",
                "message": "Minimum validation required families match bundle adapter families."
                if required_families == adapter_families
                else "Minimum validation required families must match bundle adapter families.",
                "details": {
                    "required_adapter_families": sorted(required_families),
                    "adapter_families": sorted(adapter_families),
                },
            },
            {
                "id": "heldout_validation_covers_required_families",
                "status": "pass" if covered_families >= required_families else "fail",
                "message": "Held-out validation coverage covers every required adapter family."
                if covered_families >= required_families
                else "Held-out validation coverage must cover every required adapter family.",
                "details": {
                    "covered_families": sorted(covered_families),
                    "missing_families": sorted(required_families - covered_families),
                },
            },
        ]
    )
    failures = [check for check in checks if check["status"] != "pass"]
    return {
        "surface_id": f"{bundle_id}_manifest",
        "title": f"{bundle_id} Bundle Manifest",
        "ready": not failures,
        "status": "pass" if not failures else "fail",
        "score": len(checks) - len(failures),
        "max_score": len(checks),
        "score_percent": round(((len(checks) - len(failures)) / len(checks)) * 100, 1) if checks else 0.0,
        "checks": checks,
    }


def _family_report(
    bundle_id: str,
    *,
    gallery_path: pathlib.Path | str,
    evidence_registry_path: pathlib.Path | str,
    mock_fixtures_path: pathlib.Path | str,
    certification_policy_path: pathlib.Path | str,
) -> dict[str, Any]:
    if bundle_id in {"enterprise", "enterprise_ops_pilot"}:
        return enterprise_family.enterprise_certification_report(
            gallery_path=gallery_path,
            evidence_registry_path=evidence_registry_path,
            mock_fixtures_path=mock_fixtures_path,
            certification_policy_path=certification_policy_path,
        )
    if bundle_id == "personal_productivity":
        return personal_family.personal_certification_report(
            gallery_path=gallery_path,
            evidence_registry_path=evidence_registry_path,
            mock_fixtures_path=mock_fixtures_path,
            certification_policy_path=certification_policy_path,
        )
    if bundle_id == "government_civic":
        return civic_family.civic_certification_report(
            gallery_path=gallery_path,
            evidence_registry_path=evidence_registry_path,
            mock_fixtures_path=mock_fixtures_path,
            certification_policy_path=certification_policy_path,
        )
    raise KeyError(f"Unsupported bundle certification target: {bundle_id}")


def certify_bundle_report(
    bundle_id: str,
    *,
    gallery_path: pathlib.Path | str = DEFAULT_GALLERY,
    evidence_registry_path: pathlib.Path | str = DEFAULT_EVIDENCE_REGISTRY,
    mock_fixtures_path: pathlib.Path | str = DEFAULT_MOCK_FIXTURES,
    certification_policy_path: pathlib.Path | str | None = None,
) -> dict[str, Any]:
    canonical_id = canonicalize_bundle_id(bundle_id)
    manifest = load_bundle(canonical_id)
    policy_path = certification_policy_path or CERTIFICATION_POLICY_BY_BUNDLE[canonical_id]

    manifest_surface = _manifest_certification(canonical_id, manifest)
    layout_report = validate_adapter_layout()
    family_report = _family_report(
        canonical_id,
        gallery_path=gallery_path,
        evidence_registry_path=evidence_registry_path,
        mock_fixtures_path=mock_fixtures_path,
        certification_policy_path=policy_path,
    )
    layout_surface = {
        "surface_id": f"{canonical_id}_layout",
        "title": "Adapter and Bundle Layout",
        "ready": layout_report["valid"],
        "status": "pass" if layout_report["valid"] else "fail",
        "score": 1 if layout_report["valid"] else 0,
        "max_score": 1,
        "score_percent": 100.0 if layout_report["valid"] else 0.0,
        "checks": [
            {
                "id": "adapter_layout",
                "status": "pass" if layout_report["valid"] else "fail",
                "message": "Adapter and bundle layout validates."
                if layout_report["valid"]
                else "Adapter and bundle layout has validation issues.",
                "details": layout_report,
            }
        ],
    }

    surfaces = [manifest_surface, layout_surface, *family_report.get("surfaces", [])]
    failures = [surface for surface in surfaces if not surface.get("ready")]
    max_score = sum(surface.get("max_score", 0) for surface in surfaces)
    score = sum(surface.get("score", 0) for surface in surfaces)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    return {
        "bundle_certification_version": "0.1",
        "bundle_id": canonical_id,
        "requested_bundle_id": bundle_id,
        "valid": not failures,
        "ready": not failures,
        "summary": {
            "status": "pass" if not failures else "fail",
            "readiness_level": f"{canonical_id}_bundle_ready" if not failures else f"not_{canonical_id}_bundle_ready",
            "score": score,
            "max_score": max_score,
            "score_percent": score_percent,
            "surfaces": len(surfaces),
            "failures": len(failures),
        },
        "manifest": {
            "core_adapter_ids": manifest.get("core_adapter_ids", []),
            "required_evidence_connectors": manifest.get("required_evidence_connectors", []),
            "human_review_required_for": manifest.get("human_review_required_for", []),
            "minimum_validation": manifest.get("minimum_validation", {}),
        },
        "family_certification": {
            "valid": family_report.get("valid"),
            "ready": family_report.get("ready"),
            "summary": family_report.get("summary", {}),
        },
        "surfaces": surfaces,
    }


def certification_targets() -> tuple[str, ...]:
    return BUNDLE_IDS


def certification_target_choices() -> tuple[str, ...]:
    return tuple(sorted((*BUNDLE_IDS, *BUNDLE_ALIASES)))
