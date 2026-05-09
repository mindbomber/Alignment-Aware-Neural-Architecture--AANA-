"""Packaging boundary and release checklist validation for AANA."""

from __future__ import annotations

import json
import pathlib
import tomllib
from typing import Any


PACKAGING_HARDENING_VERSION = "aana.packaging_hardening.v1"
REQUIRED_SURFACES = {
    "python_package",
    "typescript_sdk",
    "fastapi_service",
    "benchmark_eval_tooling",
    "docs_and_cards",
}
REQUIRED_RELEASE_TARGETS = {"pypi", "npm", "huggingface"}
REQUIRED_RENAME_RULES = {
    "keep_import_package_aana_stable",
    "publish_deprecation_notice_before_distribution_rename",
    "keep_old_distribution_available_for_migration_window",
    "do_not_break_cli_entrypoints_without_aliases",
}
RUNTIME_ENTRYPOINTS = {"aana", "aana-server", "aana-fastapi"}
EVAL_ENTRYPOINT_PREFIXES = (
    "aana-privacy-",
    "aana-grounded-",
    "aana-agent-tool-use-",
    "aana-validate-hf-",
    "aana-validate-cross-domain-",
)


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _load_pyproject(root: pathlib.Path) -> dict[str, Any]:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))


def _path_exists(root: pathlib.Path, relative_path: str) -> bool:
    return (root / relative_path).exists()


def validate_packaging_hardening(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    """Validate packaging boundaries and pre-publication checklist coverage."""

    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []

    if manifest.get("schema_version") != PACKAGING_HARDENING_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {PACKAGING_HARDENING_VERSION}."))

    pyproject = _load_pyproject(root_path)
    project = pyproject.get("project", {})
    scripts = project.get("scripts", {})
    optional = project.get("optional-dependencies", {})

    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list):
        issues.append(_issue("error", "surfaces", "Packaging manifest must include a surfaces list."))
        surfaces = []
    surface_by_id = {
        surface.get("id"): surface
        for surface in surfaces
        if isinstance(surface, dict) and isinstance(surface.get("id"), str)
    }
    missing_surfaces = sorted(REQUIRED_SURFACES - set(surface_by_id))
    for surface_id in missing_surfaces:
        issues.append(_issue("error", "surfaces", f"Missing required packaging surface: {surface_id}"))

    for surface_id, surface in surface_by_id.items():
        base = f"surfaces.{surface_id}"
        if surface_id not in REQUIRED_SURFACES:
            issues.append(_issue("error", f"{base}.id", f"Unknown packaging surface: {surface_id}"))
        if not _has_text(surface.get("purpose")):
            issues.append(_issue("error", f"{base}.purpose", "Surface must declare a purpose."))
        paths = surface.get("paths")
        if not _nonempty_list(paths):
            issues.append(_issue("error", f"{base}.paths", "Surface must declare paths."))
        elif require_existing_artifacts:
            for path in paths:
                if not isinstance(path, str) or not _path_exists(root_path, path):
                    issues.append(_issue("error", f"{base}.paths", f"Missing surface artifact: {path}"))

    python_surface = surface_by_id.get("python_package", {})
    if python_surface:
        if python_surface.get("current_distribution") != project.get("name"):
            issues.append(_issue("error", "surfaces.python_package.current_distribution", "Current distribution must match pyproject project.name."))
        if python_surface.get("import_package") != "aana":
            issues.append(_issue("error", "surfaces.python_package.import_package", "Public import package must remain aana."))
        for entrypoint in sorted(RUNTIME_ENTRYPOINTS):
            if entrypoint not in scripts:
                issues.append(_issue("error", "surfaces.python_package.entrypoints", f"Missing runtime entrypoint: {entrypoint}"))
        if "api" not in optional:
            issues.append(_issue("error", "surfaces.python_package.optional_extras", "Python package must keep FastAPI service dependencies in the api extra."))
        if "eval" not in optional:
            issues.append(_issue("error", "surfaces.python_package.optional_extras", "Python package must expose eval tooling dependencies through an eval extra."))

    typescript_surface = surface_by_id.get("typescript_sdk", {})
    if typescript_surface:
        package_path = root_path / "sdk/typescript/package.json"
        package = _load_json(package_path) if package_path.exists() else {}
        if package.get("name") != typescript_surface.get("package"):
            issues.append(_issue("error", "surfaces.typescript_sdk.package", "TypeScript package name must match sdk/typescript/package.json."))
        if "build" not in package.get("scripts", {}):
            issues.append(_issue("error", "surfaces.typescript_sdk.scripts", "TypeScript SDK must define a build script."))

    fastapi_surface = surface_by_id.get("fastapi_service", {})
    if fastapi_surface:
        if fastapi_surface.get("python_extra") != "api":
            issues.append(_issue("error", "surfaces.fastapi_service.python_extra", "FastAPI service must be tied to the api extra."))
        if fastapi_surface.get("entrypoint") != "aana-fastapi":
            issues.append(_issue("error", "surfaces.fastapi_service.entrypoint", "FastAPI service entrypoint must be aana-fastapi."))

    eval_surface = surface_by_id.get("benchmark_eval_tooling", {})
    if eval_surface:
        if eval_surface.get("python_extra") != "eval":
            issues.append(_issue("error", "surfaces.benchmark_eval_tooling.python_extra", "Benchmark/eval tooling must be tied to the eval extra."))
        eval_entrypoints = [name for name in scripts if name.startswith(EVAL_ENTRYPOINT_PREFIXES)]
        if not eval_entrypoints:
            issues.append(_issue("error", "surfaces.benchmark_eval_tooling.entrypoints", "Benchmark/eval tooling must remain identifiable by eval-specific entrypoints."))
        if eval_surface.get("public_claim_boundary") != "not_runtime_core":
            issues.append(_issue("error", "surfaces.benchmark_eval_tooling.public_claim_boundary", "Benchmark/eval tooling must not be described as runtime core."))

    docs_surface = surface_by_id.get("docs_and_cards", {})
    if docs_surface:
        for required in ("docs/huggingface-model-card.md", "docs/huggingface-dataset-card.md", "docs/aana-standard-publication.md"):
            if required not in docs_surface.get("paths", []):
                issues.append(_issue("error", "surfaces.docs_and_cards.paths", f"Docs/cards surface must include {required}."))

    rename_plan = manifest.get("distribution_rename_plan")
    if not isinstance(rename_plan, dict):
        issues.append(_issue("error", "distribution_rename_plan", "Manifest must include distribution_rename_plan."))
        rename_plan = {}
    if rename_plan.get("current_distribution") != project.get("name"):
        issues.append(_issue("error", "distribution_rename_plan.current_distribution", "Rename plan must match current pyproject distribution."))
    if rename_plan.get("rename_now") is not False:
        issues.append(_issue("error", "distribution_rename_plan.rename_now", "Distribution rename must not happen in this hardening pass."))
    rules = set(rename_plan.get("required_migration_rules") or [])
    missing_rules = sorted(REQUIRED_RENAME_RULES - rules)
    for rule in missing_rules:
        issues.append(_issue("error", "distribution_rename_plan.required_migration_rules", f"Missing rename migration rule: {rule}"))

    checklist = manifest.get("release_checklist")
    if not isinstance(checklist, list):
        issues.append(_issue("error", "release_checklist", "Manifest must include a release_checklist list."))
        checklist = []
    targets = set()
    for index, item in enumerate(checklist):
        base = f"release_checklist[{index}]"
        if not isinstance(item, dict):
            issues.append(_issue("error", base, "Checklist item must be an object."))
            continue
        target = item.get("target")
        targets.add(str(target))
        if target not in REQUIRED_RELEASE_TARGETS:
            issues.append(_issue("error", f"{base}.target", f"target must be one of {sorted(REQUIRED_RELEASE_TARGETS)}."))
        if item.get("status") != "required_before_publication":
            issues.append(_issue("error", f"{base}.status", "Checklist status must be required_before_publication."))
        if not _nonempty_list(item.get("required_checks")):
            issues.append(_issue("error", f"{base}.required_checks", "Checklist item must include required checks."))
        if item.get("human_release_review_required") is not True:
            issues.append(_issue("error", f"{base}.human_release_review_required", "Human release review must be required."))
    for missing in sorted(REQUIRED_RELEASE_TARGETS - targets):
        issues.append(_issue("error", "release_checklist", f"Missing release checklist target: {missing}"))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "surface_count": len(surfaces),
        "release_target_count": len(targets & REQUIRED_RELEASE_TARGETS),
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    return _load_json(pathlib.Path(path))


__all__ = ["PACKAGING_HARDENING_VERSION", "load_manifest", "validate_packaging_hardening"]
