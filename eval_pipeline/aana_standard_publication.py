"""Validation helpers for the AANA standard publication package."""

from __future__ import annotations

import argparse
import json
import pathlib
import tomllib
from dataclasses import dataclass
from typing import Any


PUBLIC_ARCHITECTURE_CLAIM = (
    "AANA makes agents more auditable, safer, more grounded, and more controllable."
)
PUBLIC_EVIDENCE_BOUNDARY = (
    "AANA is production-candidate as an audit/control/verification/correction layer. "
    "AANA is not yet proven as a raw agent-performance engine and must not be "
    "claimed to have raw agent-performance superiority."
)
MANIFEST_VERSION = "aana.standard_publication.v1"
REQUIRED_COMPONENT_IDS = {
    "python_package",
    "typescript_sdk",
    "fastapi_service",
    "benchmark_eval_tooling",
    "model_dataset_cards",
    "agent_action_contract_spec",
}
AGENT_ACTION_REQUIRED_FIELDS = [
    "tool_name",
    "tool_category",
    "authorization_state",
    "evidence_refs",
    "risk_domain",
    "proposed_arguments",
    "recommended_route",
]
PUBLIC_CLAIM_SURFACES = [
    "README.md",
    "docs/index.html",
    "docs/aana-standard-publication.md",
    "docs/aana-public-artifact-hub.md",
    "docs/aana-agent-action-technical-report.md",
    "docs/aana-agent-contract-sdk.md",
    "docs/agent-action-contract-quickstart.md",
    "docs/huggingface-model-card.md",
    "docs/huggingface-dataset-card.md",
]
OLD_PUBLIC_ARCHITECTURE_CLAIM = (
    "AANA is an architecture for making agents more auditable, safer, "
    "more grounded, and more controllable."
)


@dataclass(frozen=True)
class PublicationValidationResult:
    """Summary returned by the publication validator."""

    manifest_path: str
    ok: bool
    checked_components: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "ok": self.ok,
            "checked_components": self.checked_components,
            "errors": self.errors,
        }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    manifest_path = pathlib.Path(path)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_standard_publication(
    manifest_path: str | pathlib.Path = "examples/aana_standard_publication_manifest.json",
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> PublicationValidationResult:
    """Validate that AANA's public standard/package surfaces are coherent."""

    root_path = pathlib.Path(root)
    manifest_file = pathlib.Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root_path / manifest_file
    manifest = load_manifest(manifest_file)

    errors: list[str] = []
    if manifest.get("schema_version") != MANIFEST_VERSION:
        errors.append(f"manifest schema_version must be {MANIFEST_VERSION!r}")
    if manifest.get("public_claim") != PUBLIC_ARCHITECTURE_CLAIM:
        errors.append("manifest public_claim does not match the approved AANA architecture claim")
    if manifest.get("evidence_boundary") != PUBLIC_EVIDENCE_BOUNDARY:
        errors.append("manifest evidence_boundary does not match the approved evidence boundary")

    components = manifest.get("components")
    if not isinstance(components, list):
        components = []
        errors.append("manifest components must be a list")

    component_by_id = {
        component.get("id"): component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    missing = sorted(REQUIRED_COMPONENT_IDS - set(component_by_id))
    if missing:
        errors.append(f"manifest missing required components: {', '.join(missing)}")

    for component in component_by_id.values():
        _validate_required_paths(component, root_path, require_existing_artifacts, errors)

    if "python_package" in component_by_id:
        _validate_python_package(component_by_id["python_package"], root_path, errors)
    if "typescript_sdk" in component_by_id:
        _validate_typescript_sdk(component_by_id["typescript_sdk"], root_path, errors)
    if "fastapi_service" in component_by_id:
        _validate_fastapi_service(component_by_id["fastapi_service"], root_path, errors)
    if "model_dataset_cards" in component_by_id:
        _validate_model_dataset_cards(component_by_id["model_dataset_cards"], root_path, errors)
    if "agent_action_contract_spec" in component_by_id:
        _validate_agent_action_contract(component_by_id["agent_action_contract_spec"], root_path, errors)
    if "benchmark_eval_tooling" in component_by_id:
        _validate_benchmark_eval_tooling(component_by_id["benchmark_eval_tooling"], root_path, errors)
    _validate_public_claim_surfaces(root_path, errors)

    return PublicationValidationResult(
        manifest_path=str(manifest_file),
        ok=not errors,
        checked_components=sorted(component_by_id),
        errors=errors,
    )


def _validate_required_paths(
    component: dict[str, Any],
    root: pathlib.Path,
    require_existing_artifacts: bool,
    errors: list[str],
) -> None:
    paths = component.get("required_paths", [])
    if not isinstance(paths, list) or not paths:
        errors.append(f"{component.get('id', '<unknown>')} must declare required_paths")
        return
    if not require_existing_artifacts:
        return
    for raw_path in paths:
        if not isinstance(raw_path, str):
            errors.append(f"{component.get('id', '<unknown>')} has a non-string required path")
            continue
        if not (root / raw_path).exists():
            errors.append(f"{component.get('id', '<unknown>')} missing required artifact: {raw_path}")


def _validate_python_package(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        errors.append("python_package missing pyproject.toml")
        return
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    if project.get("name") != component.get("distribution"):
        errors.append("python_package distribution does not match pyproject project.name")
    if "auditable" not in project.get("description", ""):
        errors.append("python_package description should express AANA's audit/control direction")
    scripts = project.get("scripts", {})
    for script in component.get("required_scripts", []):
        if script not in scripts:
            errors.append(f"python_package missing script: {script}")
    optional_dependencies = project.get("optional-dependencies", {})
    api_dependencies = " ".join(optional_dependencies.get("api", [])).lower()
    if "fastapi" not in api_dependencies or "uvicorn" not in api_dependencies:
        errors.append("python_package api extra must include fastapi and uvicorn")
    package_include = pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
    if "aana*" not in package_include:
        errors.append("python_package must include the aana import package")


def _validate_typescript_sdk(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    package_path = root / "sdk/typescript/package.json"
    if not package_path.exists():
        errors.append("typescript_sdk missing package.json")
        return
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if package.get("name") != component.get("package"):
        errors.append("typescript_sdk package name does not match manifest")
    if "Agent Action Contract" not in package.get("description", ""):
        errors.append("typescript_sdk description should mention Agent Action Contract")
    scripts = package.get("scripts", {})
    for script in component.get("required_scripts", []):
        if script not in scripts:
            errors.append(f"typescript_sdk missing script: {script}")


def _validate_fastapi_service(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    docs_path = root / "docs/fastapi-service.md"
    if not docs_path.exists():
        errors.append("fastapi_service missing docs/fastapi-service.md")
        return
    docs = docs_path.read_text(encoding="utf-8")
    for route in component.get("required_routes", []):
        if route not in docs:
            errors.append(f"fastapi_service docs missing route: {route}")
    for phrase in ("token auth", "redacted JSONL audit", "/docs"):
        if phrase.lower() not in docs.lower():
            errors.append(f"fastapi_service docs missing phrase: {phrase}")


def _validate_benchmark_eval_tooling(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    boundary = str(component.get("boundary", "")).lower()
    if "separate" not in boundary or "runtime" not in boundary:
        errors.append("benchmark_eval_tooling must declare separation from the runtime SDK/API claim")
    for path in component.get("required_paths", []):
        if isinstance(path, str) and not (root / path).exists():
            errors.append(f"benchmark_eval_tooling missing required artifact: {path}")


def _validate_model_dataset_cards(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    cards = component.get("cards", [])
    if not isinstance(cards, list) or not cards:
        errors.append("model_dataset_cards must declare cards")
        return
    seen_types: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            errors.append("model_dataset_cards contains a non-object card")
            continue
        card_type = card.get("type")
        card_path = card.get("path")
        seen_types.add(str(card_type))
        if not isinstance(card_path, str):
            errors.append(f"model_dataset_cards {card_type!r} card missing path")
            continue
        resolved = root / card_path
        if not resolved.exists():
            errors.append(f"model_dataset_cards missing card: {card_path}")
            continue
        text = resolved.read_text(encoding="utf-8")
        if PUBLIC_ARCHITECTURE_CLAIM not in text:
            errors.append(f"{card_path} missing public architecture claim")
        if "not yet proven as a raw agent-performance engine" not in text:
            errors.append(f"{card_path} missing raw agent-performance boundary")
        if "raw agent-performance superiority" not in text:
            errors.append(f"{card_path} missing raw agent-performance superiority boundary")
    if {"model", "dataset"} - seen_types:
        errors.append("model_dataset_cards must include both model and dataset card templates")


def _validate_public_claim_surfaces(root: pathlib.Path, errors: list[str]) -> None:
    for surface in PUBLIC_CLAIM_SURFACES:
        path = root / surface
        if not path.exists():
            errors.append(f"public claim surface missing: {surface}")
            continue
        text = path.read_text(encoding="utf-8")
        if PUBLIC_ARCHITECTURE_CLAIM not in text:
            errors.append(f"{surface} missing exact public architecture claim")
        if OLD_PUBLIC_ARCHITECTURE_CLAIM in text:
            errors.append(f"{surface} still uses the old public architecture claim")


def _validate_agent_action_contract(component: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    expected_fields = component.get("required_fields")
    if expected_fields != AGENT_ACTION_REQUIRED_FIELDS:
        errors.append("agent_action_contract_spec required_fields must match the public seven-field order")

    schema_path = root / "schemas/agent_tool_precheck.schema.json"
    if not schema_path.exists():
        errors.append("agent_action_contract_spec missing JSON schema")
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("title") != "AANA Agent Action Contract v1":
        errors.append("agent_action_contract_spec schema title must be AANA Agent Action Contract v1")
    if schema.get("$id") != "https://aana.dev/schemas/agent_action_contract_v1.schema.json":
        errors.append("agent_action_contract_spec schema $id must use the public AANA contract URL")
    if schema.get("required") != AGENT_ACTION_REQUIRED_FIELDS:
        errors.append("agent_action_contract_spec schema required fields must be the seven-field public contract")
    if "schema_version" in schema.get("required", []):
        errors.append("agent_action_contract_spec schema_version must stay optional for compatibility")

    docs_path = root / "docs/agent-action-contract-v1.md"
    if docs_path.exists():
        docs = docs_path.read_text(encoding="utf-8")
        if "Stable Fields" not in docs:
            errors.append("agent_action_contract_spec docs must include Stable Fields")
        for field in AGENT_ACTION_REQUIRED_FIELDS:
            if f"`{field}`" not in docs:
                errors.append(f"agent_action_contract_spec docs missing field: {field}")
    else:
        errors.append("agent_action_contract_spec missing docs/agent-action-contract-v1.md")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="examples/aana_standard_publication_manifest.json",
        help="Path to the AANA standard publication manifest.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root used to resolve manifest artifact paths.",
    )
    parser.add_argument(
        "--require-existing-artifacts",
        action="store_true",
        help="Fail if any artifact path declared in the manifest is missing.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full validation result as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = validate_standard_publication(
        args.manifest,
        root=args.root,
        require_existing_artifacts=args.require_existing_artifacts,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    elif result.ok:
        print(
            "AANA standard publication package is valid: "
            f"{len(result.checked_components)} components checked."
        )
    else:
        print("AANA standard publication package is invalid:")
        for error in result.errors:
            print(f"- {error}")
    return 0 if result.ok else 1
