#!/usr/bin/env python3
"""Validate AANA versioned surfaces and migration notes."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_contract, aix, audit, evidence_integrations, runtime, workflow_contract
from eval_pipeline.adapter_runner import verifier_modules


DEFAULT_POLICY = ROOT / "examples" / "version_migration_policy.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "examples" / "evidence_registry.json"
SEMVERISH = re.compile(r"^\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?$")
REQUIRED_SURFACES = {
    "adapter_version",
    "workflow_contract_version",
    "agent_event_contract_version",
    "verifier_module_version",
    "route_map_version",
    "aix_tuning_version",
    "evidence_connector_manifest_version",
    "audit_schema_version",
    "runtime_version",
}
REQUIRED_COMPATIBILITY_TESTS = {
    "tests.test_public_api_freeze",
    "tests.test_runtime_api",
    "tests.test_adapter_runner_golden_outputs",
    "tests.test_evidence_integrations",
    "tests.test_support_audit_logging",
    "tests.test_versioning_migration",
}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _valid_version(value):
    return isinstance(value, str) and bool(SEMVERISH.match(value))


def _adapter_versions():
    versions = {}
    for path in sorted((ROOT / "examples").glob("*_adapter.json")):
        payload = load_json(path)
        versions[path.name] = payload.get("version")
    return versions


def validate_versioning_migration(path=DEFAULT_POLICY, evidence_registry=DEFAULT_EVIDENCE_REGISTRY):
    policy = load_json(path)
    registry = load_json(evidence_registry)
    errors = []

    surfaces = policy.get("versioned_surfaces", {})
    missing_surfaces = sorted(REQUIRED_SURFACES - set(surfaces))
    if missing_surfaces:
        errors.append(f"versioned_surfaces missing: {', '.join(missing_surfaces)}")

    expected_versions = {
        "workflow_contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
        "agent_event_contract_version": agent_contract.AGENT_EVENT_VERSION,
        "verifier_module_version": verifier_modules.VERIFIER_MODULE_VERSION,
        "route_map_version": verifier_modules.ROUTE_MAP_VERSION,
        "aix_tuning_version": aix.AIX_VERSION,
        "evidence_connector_manifest_version": evidence_integrations.CONNECTOR_CONTRACT_VERSION,
        "audit_schema_version": audit.AUDIT_RECORD_VERSION,
        "runtime_version": runtime.RUNTIME_API_VERSION,
    }
    for surface, expected in expected_versions.items():
        current = surfaces.get(surface, {}).get("current")
        if current != expected:
            errors.append(f"{surface}.current must match code version {expected!r}.")
        if not _valid_version(current):
            errors.append(f"{surface}.current must be a version string.")

    adapter_versions = _adapter_versions()
    missing_adapter_versions = sorted(name for name, version in adapter_versions.items() if not _valid_version(version))
    if missing_adapter_versions:
        errors.append(f"adapter files missing valid version: {', '.join(missing_adapter_versions)}")
    adapter_current = surfaces.get("adapter_version", {}).get("current")
    if not _valid_version(adapter_current):
        errors.append("adapter_version.current must be a version string.")

    registry_version = registry.get("registry_version")
    evidence_current = surfaces.get("evidence_connector_manifest_version", {}).get("current")
    if registry_version != evidence_current:
        errors.append("examples/evidence_registry.json registry_version must match evidence_connector_manifest_version.current.")

    verifier_versions = getattr(verifier_modules, "VERIFIER_MODULE_VERSIONS", {})
    route_versions = getattr(verifier_modules, "ROUTE_MAP_VERSIONS", {})
    for module_name in ("business_ops", "customer_comms", "engineering_release", "local_actions", "regulated_advice", "research_civic", "support_product"):
        if verifier_versions.get(module_name) != verifier_modules.VERIFIER_MODULE_VERSION:
            errors.append(f"verifier module {module_name} must declare version {verifier_modules.VERIFIER_MODULE_VERSION}.")
        if route_versions.get(module_name) != verifier_modules.ROUTE_MAP_VERSION:
            errors.append(f"route map {module_name} must declare version {verifier_modules.ROUTE_MAP_VERSION}.")

    compatibility_tests = set(policy.get("compatibility_tests", []))
    missing_tests = sorted(REQUIRED_COMPATIBILITY_TESTS - compatibility_tests)
    if missing_tests:
        errors.append(f"compatibility_tests missing: {', '.join(missing_tests)}")

    for surface_name, surface in surfaces.items():
        requirements = surface.get("breaking_change_requires", [])
        if not isinstance(requirements, list) or not requirements:
            errors.append(f"{surface_name}: breaking_change_requires must be non-empty.")
        requirement_text = " ".join(requirements).lower()
        if "migration note" not in requirement_text:
            errors.append(f"{surface_name}: breaking_change_requires must include migration note.")
        if "test" not in requirement_text and "golden-output" not in requirement_text:
            errors.append(f"{surface_name}: breaking_change_requires must include compatibility test coverage.")

    breaking_policy = policy.get("breaking_change_policy", {})
    for key in ("requires_migration_note", "requires_compatibility_test", "requires_version_bump"):
        if breaking_policy.get(key) is not True:
            errors.append(f"breaking_change_policy.{key} must be true.")

    notes = policy.get("migration_notes", [])
    if not notes:
        errors.append("migration_notes must contain at least the initial version note.")
    for index, note in enumerate(notes):
        label = note.get("version", f"index {index}")
        if not _valid_version(note.get("version")):
            errors.append(f"migration_notes[{index}].version must be a version string.")
        if note.get("breaking") is True:
            if not str(note.get("migration", "")).strip():
                errors.append(f"migration note {label}: breaking changes require migration text.")
            if not note.get("compatibility_tests"):
                errors.append(f"migration note {label}: breaking changes require compatibility_tests.")
        if not str(note.get("summary", "")).strip():
            errors.append(f"migration note {label}: summary is required.")

    release_gate = policy.get("release_gate", {})
    if release_gate.get("script") != "scripts/validation/validate_versioning_migration.py":
        errors.append("release_gate.script must point to scripts/validation/validate_versioning_migration.py.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "surface_count": len(surfaces),
        "required_surfaces": sorted(REQUIRED_SURFACES),
        "adapter_count": len(adapter_versions),
        "runtime_version": runtime.RUNTIME_API_VERSION,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="Versioning and migration policy JSON artifact.")
    parser.add_argument("--evidence-registry", default=DEFAULT_EVIDENCE_REGISTRY, help="Evidence registry JSON artifact.")
    args = parser.parse_args(argv)
    report = validate_versioning_migration(args.policy, evidence_registry=args.evidence_registry)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
