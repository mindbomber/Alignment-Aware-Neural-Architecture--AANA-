"""Validation helpers for AANA adapter-family and bundle manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aana.adapters import FAMILY_IDS, load_adapter_families
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, aliases_for_bundle, canonicalize_bundle_id, load_bundles
from aana.canonical_ids import validate_canonical_ids


CLAIM_USES = {"external_reporting"}
TUNING_USES = {"calibration"}


@dataclass(frozen=True)
class LayoutIssue:
    code: str
    message: str


def _split_set(dataset: dict[str, Any], key: str) -> set[str]:
    return {str(item) for item in dataset.get(key, [])}


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value) and bool(value)


def _family_has_heldout_coverage(family: dict[str, Any]) -> bool:
    for dataset in family.get("hf_datasets", []):
        if _split_set(dataset, "heldout_validation") or _split_set(dataset, "external_reporting"):
            return True
    return False


def validate_adapter_layout() -> dict[str, Any]:
    adapter_families = load_adapter_families()
    bundles = load_bundles()
    issues: list[LayoutIssue] = []

    missing_families = set(FAMILY_IDS) - set(adapter_families)
    if missing_families:
        issues.append(LayoutIssue("missing_adapter_family", f"Missing adapter families: {sorted(missing_families)}"))

    for family_id, family in adapter_families.items():
        if family.get("family_id") != family_id:
            issues.append(LayoutIssue("family_id_mismatch", f"{family_id} manifest has family_id={family.get('family_id')}"))
        if not family.get("primary_metrics"):
            issues.append(LayoutIssue("missing_metrics", f"{family_id} does not declare primary_metrics"))
        for dataset in family.get("hf_datasets", []):
            calibration = _split_set(dataset, "calibration")
            heldout = _split_set(dataset, "heldout_validation")
            external = _split_set(dataset, "external_reporting")
            tune_claim_overlap = calibration & external
            tune_validation_overlap = calibration & heldout
            if tune_claim_overlap:
                issues.append(
                    LayoutIssue(
                        "same_split_for_tuning_and_public_claims",
                        f"{family_id}:{dataset.get('dataset_name')} reuses {sorted(tune_claim_overlap)} for calibration and external_reporting",
                    )
                )
            if tune_validation_overlap:
                issues.append(
                    LayoutIssue(
                        "same_split_for_tuning_and_heldout_validation",
                        f"{family_id}:{dataset.get('dataset_name')} reuses {sorted(tune_validation_overlap)} for calibration and heldout_validation",
                    )
                )

    for bundle_id, bundle in bundles.items():
        if bundle.get("bundle_id") != bundle_id:
            issues.append(LayoutIssue("bundle_id_mismatch", f"{bundle_id} manifest has bundle_id={bundle.get('bundle_id')}"))
        if bundle.get("canonical_id") != bundle_id:
            issues.append(
                LayoutIssue(
                    "bundle_canonical_id_mismatch",
                    f"{bundle_id} manifest has canonical_id={bundle.get('canonical_id')}",
                )
            )
        expected_aliases = aliases_for_bundle(bundle_id)
        if sorted(bundle.get("aliases", [])) != expected_aliases:
            issues.append(
                LayoutIssue(
                    "bundle_alias_mismatch",
                    f"{bundle_id} manifest aliases={bundle.get('aliases')} expected={expected_aliases}",
                )
            )
        for key in ("core_adapter_ids", "required_evidence_connectors", "human_review_required_for"):
            if not _nonempty_list(bundle.get(key)):
                issues.append(LayoutIssue("bundle_missing_required_field", f"{bundle_id} must declare non-empty {key}."))
        minimum_validation = bundle.get("minimum_validation")
        if not isinstance(minimum_validation, dict):
            issues.append(LayoutIssue("bundle_missing_minimum_validation", f"{bundle_id} must declare minimum_validation."))
            minimum_validation = {}
        required_families = minimum_validation.get("required_adapter_families")
        if not _nonempty_list(required_families):
            issues.append(
                LayoutIssue(
                    "bundle_missing_required_adapter_families",
                    f"{bundle_id} minimum_validation must declare required_adapter_families.",
                )
            )
            required_families = []
        if set(required_families) != set(bundle.get("adapter_families", [])):
            issues.append(
                LayoutIssue(
                    "bundle_validation_family_mismatch",
                    f"{bundle_id} minimum_validation.required_adapter_families must match adapter_families.",
                )
            )
        coverage = minimum_validation.get("heldout_validation_coverage")
        if not isinstance(coverage, list) or not coverage:
            issues.append(
                LayoutIssue(
                    "bundle_missing_heldout_validation_coverage",
                    f"{bundle_id} must declare heldout_validation_coverage.",
                )
            )
            coverage = []
        covered_families = set()
        for index, item in enumerate(coverage):
            if not isinstance(item, dict):
                issues.append(LayoutIssue("bundle_invalid_heldout_coverage", f"{bundle_id} coverage[{index}] must be an object."))
                continue
            family_id = item.get("adapter_family")
            source = item.get("source")
            coverage_type = item.get("coverage_type")
            if family_id not in adapter_families:
                issues.append(LayoutIssue("bundle_unknown_coverage_family", f"{bundle_id} coverage references unknown family {family_id}."))
                continue
            if not isinstance(source, str) or not source.strip():
                issues.append(LayoutIssue("bundle_coverage_missing_source", f"{bundle_id} coverage for {family_id} must declare source."))
            if coverage_type not in {"hf_dataset_split", "repo_heldout_fixture", "external_reporting_artifact"}:
                issues.append(
                    LayoutIssue(
                        "bundle_coverage_invalid_type",
                        f"{bundle_id} coverage for {family_id} has invalid coverage_type={coverage_type}.",
                    )
                )
            covered_families.add(family_id)
        missing_coverage = set(bundle.get("adapter_families", [])) - covered_families
        if missing_coverage:
            issues.append(
                LayoutIssue(
                    "bundle_missing_family_heldout_coverage",
                    f"{bundle_id} lacks held-out validation coverage for {sorted(missing_coverage)}.",
                )
            )
        for family_id in bundle.get("adapter_families", []):
            if family_id not in adapter_families:
                issues.append(LayoutIssue("unknown_bundle_adapter_family", f"{bundle_id} references unknown adapter family {family_id}"))
            elif family_id != "governance_compliance" and not _family_has_heldout_coverage(adapter_families[family_id]):
                issues.append(
                    LayoutIssue(
                        "adapter_family_missing_heldout_split",
                        f"{bundle_id} references {family_id}, but that adapter family declares no heldout_validation or external_reporting split.",
                    )
                )

    for alias, target in BUNDLE_ALIASES.items():
        try:
            canonical = canonicalize_bundle_id(alias)
        except KeyError:
            issues.append(LayoutIssue("unknown_bundle_alias", f"Bundle alias {alias} does not resolve."))
            continue
        if canonical != target or canonical not in BUNDLE_IDS:
            issues.append(
                LayoutIssue(
                    "invalid_bundle_alias_target",
                    f"Bundle alias {alias} resolves to {canonical}; expected target {target} in {BUNDLE_IDS}",
                )
            )

    canonical_report = validate_canonical_ids()
    for issue in canonical_report["issues"]:
        issues.append(LayoutIssue("canonical_id_drift", f"{issue['code']}: {issue['message']}"))

    return {
        "valid": not issues,
        "adapter_families": list(adapter_families),
        "bundles": list(bundles),
        "bundle_aliases": dict(sorted(BUNDLE_ALIASES.items())),
        "issues": [issue.__dict__ for issue in issues],
    }
