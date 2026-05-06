"""Adapter registry and adapter metadata helpers."""

import json
import pathlib


DETERMINISTIC_DEMO_ADAPTER_IDS = (
    "budgeted_travel_planner",
    "allergy_safe_meal_planner",
)


def load_adapter(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        adapter = json.load(handle)
    if not isinstance(adapter, dict):
        raise ValueError("Adapter file must contain a JSON object.")
    if not adapter.get("adapter_name"):
        raise ValueError("Adapter file is missing adapter_name.")
    return adapter


def adapter_summary(adapter):
    return {
        "name": adapter.get("adapter_name"),
        "version": adapter.get("version"),
        "domain": adapter.get("domain", {}).get("name"),
    }


def adapter_match_text(adapter):
    return {
        str(adapter.get("adapter_name", "")).lower(),
        str(adapter.get("domain", {}).get("name", "")).lower(),
        str(adapter.get("domain", {}).get("user_workflow", "")).lower(),
    }


def adapter_identifier_candidates(adapter, task=None):
    identifiers = set(adapter_match_text(adapter))
    if task:
        identifiers.add(str(task.get("task_type", "")).lower())
    return {identifier for identifier in identifiers if identifier}


def _identifier_matches(adapter_id, identifiers):
    adapter_id = str(adapter_id).lower()
    return adapter_id in identifiers or any(
        identifier == adapter_id or identifier.startswith(f"{adapter_id}_")
        for identifier in identifiers
    )


def resolve_verifier_module(adapter, task, verifier_registry):
    identifiers = adapter_identifier_candidates(adapter, task)
    for name in verifier_registry.names():
        module = verifier_registry.get(name)
        if module.adapter_predicate and module.adapter_predicate(adapter):
            return module
        for adapter_id in module.supported_adapters or ():
            if _identifier_matches(adapter_id, identifiers):
                return module
    return None


def is_deterministic_demo_adapter(adapter, task=None):
    identifiers = adapter_identifier_candidates(adapter, task)
    return any(_identifier_matches(adapter_id, identifiers) for adapter_id in DETERMINISTIC_DEMO_ADAPTER_IDS)


def resolve_runtime_adapter(adapter, task, verifier_registry):
    verifier_module = resolve_verifier_module(adapter, task, verifier_registry)
    if verifier_module:
        return {
            "kind": "verifier_backed",
            "verifier_module": verifier_module,
            "adapter_ids": list(verifier_module.supported_adapters or ()),
            "family": verifier_module.family,
            "production_candidate": True,
        }
    if is_deterministic_demo_adapter(adapter, task):
        return {
            "kind": "deterministic_demo",
            "verifier_module": None,
            "adapter_ids": list(DETERMINISTIC_DEMO_ADAPTER_IDS),
            "family": "demo_only",
            "production_candidate": False,
        }
    return {
        "kind": "unsupported",
        "verifier_module": None,
        "adapter_ids": [],
        "family": None,
        "production_candidate": False,
    }
