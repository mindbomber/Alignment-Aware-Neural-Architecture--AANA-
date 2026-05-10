"""Repository organization validation for AANA."""

from __future__ import annotations

import pathlib
from typing import Any


REPO_ORGANIZATION_VERSION = "aana.repo_organization.v1"

TOP_LEVEL_SCRIPT_FILES = {
    "__init__.py",
    "aana_cli.py",
    "aana_fastapi.py",
    "aana_server.py",
    "dev.py",
    "README.md",
    "validate_aana_platform.py",
}

SCRIPT_GROUPS = {
    "adapters",
    "benchmarks",
    "demos",
    "evals",
    "hf",
    "integrations",
    "pilots",
    "publication",
    "validation",
}

SCRIPT_DIR_ALLOWLIST = SCRIPT_GROUPS | {"__pycache__"}

REQUIRED_ORGANIZATION_DOCS = {
    "docs/architecture-map.md",
    "docs/repo-organization.md",
    "docs/research-evaluation-workflows.md",
    "docs/publication-release-checklist.md",
    "docs/evidence/artifact_manifest.json",
}

STALE_PUBLIC_REFERENCES = {
    "scripts/run_adapter.py": "scripts/adapters/run_adapter.py",
    "scripts/new_adapter.py": "scripts/adapters/new_adapter.py",
    "scripts/validate_adapter.py": "scripts/validation/validate_adapter.py",
    "scripts/run_starter_pilot_kit.py": "scripts/pilots/run_starter_pilot_kit.py",
    "scripts/run_pilot_evaluation_kit.py": "scripts/pilots/run_pilot_evaluation_kit.py",
    "aana-server": "aana-fastapi or python scripts/aana_server.py",
    "aana.server:main": "aana.fastapi_app:main or aana.server runtime import",
}

CIVIC_GOVERNMENT_ALIAS_ALLOWED_PATHS = {
    "aana/bundles/government_civic/manifest.json",
    "docs/aana-public-artifact-hub.md",
    "docs/repo-organization.md",
    "eval_pipeline/repo_organization.py",
    "scripts/pilots/run_pilot_evaluation_kit.py",
    "scripts/pilots/run_starter_pilot_kit.py",
    "tests/test_adapter_layout.py",
    "tests/test_bundle_certification.py",
    "tests/test_canonical_ids.py",
}

TEXT_SUFFIXES = {".html", ".json", ".md", ".py", ".toml", ".txt", ".yml", ".yaml"}
SCAN_ROOTS = ("README.md", "docs", "examples", "tests", "eval_pipeline", "scripts", "aana", "pyproject.toml")
SKIP_DIR_NAMES = {".git", ".mypy_cache", ".pytest_cache", "__pycache__", "build", "dist", "node_modules", ".venv", "venv"}
POLICY_SOURCE_PATHS = {"eval_pipeline/repo_organization.py"}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _relative(path: pathlib.Path, root: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_text_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for scan_root in SCAN_ROOTS:
        path = root / scan_root
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
            continue
        for child in path.rglob("*"):
            if any(part in SKIP_DIR_NAMES for part in child.parts):
                continue
            if child.is_file() and child.suffix.lower() in TEXT_SUFFIXES:
                files.append(child)
    return sorted(set(files))


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def validate_repo_organization(*, root: str | pathlib.Path = ".") -> dict[str, Any]:
    """Validate that repo cleanup decisions remain canonical and enforceable."""

    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []

    scripts_path = root_path / "scripts"
    if not scripts_path.exists():
        issues.append(_issue("error", "scripts", "Missing scripts directory."))
    else:
        observed_files = {path.name for path in scripts_path.iterdir() if path.is_file()}
        observed_dirs = {path.name for path in scripts_path.iterdir() if path.is_dir()}
        unknown_files = sorted(observed_files - TOP_LEVEL_SCRIPT_FILES)
        unknown_dirs = sorted(observed_dirs - SCRIPT_DIR_ALLOWLIST)
        missing_dirs = sorted(SCRIPT_GROUPS - observed_dirs)
        for name in unknown_files:
            issues.append(_issue("error", f"scripts/{name}", "Top-level scripts must stay limited to runtime/compatibility entrypoints; move grouped tooling into scripts/<group>/."))
        for name in unknown_dirs:
            issues.append(_issue("error", f"scripts/{name}", "Unknown scripts subdirectory; use the canonical script groups or update the repo organization policy."))
        for name in missing_dirs:
            issues.append(_issue("error", f"scripts/{name}", "Missing canonical scripts subdirectory."))

    for doc_path in sorted(REQUIRED_ORGANIZATION_DOCS):
        if not (root_path / doc_path).exists():
            issues.append(_issue("error", doc_path, "Missing required repository organization or evidence-policy artifact."))

    text_files = _iter_text_files(root_path)
    for path in text_files:
        relative = _relative(path, root_path)
        text = _read_text(path)
        if relative not in POLICY_SOURCE_PATHS:
            for stale, replacement in STALE_PUBLIC_REFERENCES.items():
                if stale in text:
                    issues.append(_issue("error", relative, f"Stale public reference `{stale}` found; use `{replacement}`."))
        if "civic_government" in text and relative not in CIVIC_GOVERNMENT_ALIAS_ALLOWED_PATHS:
            issues.append(_issue("error", relative, "`civic_government` must appear only in backward-compatible alias surfaces; public paths/docs should use `government_civic`."))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "schema_version": REPO_ORGANIZATION_VERSION,
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "top_level_script_files": sorted(TOP_LEVEL_SCRIPT_FILES),
        "script_groups": sorted(SCRIPT_GROUPS),
        "required_docs": sorted(REQUIRED_ORGANIZATION_DOCS),
        "scanned_file_count": len(text_files),
    }
