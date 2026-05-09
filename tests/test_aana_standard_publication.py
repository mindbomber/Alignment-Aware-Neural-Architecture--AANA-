import json
import pathlib

from eval_pipeline.aana_standard_publication import (
    PUBLIC_ARCHITECTURE_CLAIM,
    validate_standard_publication,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_standard_publication_manifest_is_valid() -> None:
    result = validate_standard_publication(
        ROOT / "examples/aana_standard_publication_manifest.json",
        root=ROOT,
        require_existing_artifacts=True,
    )

    assert result.ok, result.errors
    assert result.checked_components == [
        "agent_action_contract_spec",
        "benchmark_eval_tooling",
        "fastapi_service",
        "model_dataset_cards",
        "python_package",
        "typescript_sdk",
    ]


def test_standard_publication_blocks_missing_required_component(tmp_path: pathlib.Path) -> None:
    manifest = json.loads((ROOT / "examples/aana_standard_publication_manifest.json").read_text())
    manifest["components"] = [
        component for component in manifest["components"] if component["id"] != "typescript_sdk"
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_standard_publication(manifest_path, root=ROOT)

    assert not result.ok
    assert any("typescript_sdk" in error for error in result.errors)


def test_standard_publication_blocks_unapproved_public_claim(tmp_path: pathlib.Path) -> None:
    manifest = json.loads((ROOT / "examples/aana_standard_publication_manifest.json").read_text())
    manifest["public_claim"] = PUBLIC_ARCHITECTURE_CLAIM + " It is a raw performance engine."
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_standard_publication(manifest_path, root=ROOT)

    assert not result.ok
    assert "public_claim" in " ".join(result.errors)


def test_standard_publication_requires_card_boundary(tmp_path: pathlib.Path) -> None:
    card = tmp_path / "model-card.md"
    card.write_text(PUBLIC_ARCHITECTURE_CLAIM, encoding="utf-8")
    manifest = json.loads((ROOT / "examples/aana_standard_publication_manifest.json").read_text())
    for component in manifest["components"]:
        if component["id"] == "model_dataset_cards":
            component["cards"][0]["path"] = str(card)
            component["required_paths"][0] = str(card)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_standard_publication(manifest_path, root=ROOT)

    assert not result.ok
    assert any("raw agent-performance boundary" in error for error in result.errors)
