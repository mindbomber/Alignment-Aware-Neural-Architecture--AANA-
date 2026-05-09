"""Validation helpers for AANA adapter-family and bundle manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aana.adapters import FAMILY_IDS, load_adapter_families
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, aliases_for_bundle, canonicalize_bundle_id, load_bundles


CLAIM_USES = {"external_reporting"}
TUNING_USES = {"calibration"}


@dataclass(frozen=True)
class LayoutIssue:
    code: str
    message: str


def _split_set(dataset: dict[str, Any], key: str) -> set[str]:
    return {str(item) for item in dataset.get(key, [])}


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
        for family_id in bundle.get("adapter_families", []):
            if family_id not in adapter_families:
                issues.append(LayoutIssue("unknown_bundle_adapter_family", f"{bundle_id} references unknown adapter family {family_id}"))

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

    return {
        "valid": not issues,
        "adapter_families": list(adapter_families),
        "bundles": list(bundles),
        "bundle_aliases": dict(sorted(BUNDLE_ALIASES.items())),
        "issues": [issue.__dict__ for issue in issues],
    }
