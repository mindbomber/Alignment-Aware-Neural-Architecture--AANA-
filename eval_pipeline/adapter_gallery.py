"""Published adapter gallery metadata for docs and bridge surfaces."""

from __future__ import annotations

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLISHED_GALLERY_VERSION = "0.1"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
PRODUCTION_POSITIONING = (
    "Catalog status is not production certification. This repository can be demo-ready, pilot-ready, "
    "or production-candidate for controlled evaluation, but it is not production-certified by local "
    "tests alone. Production readiness requires live evidence connectors, domain owner signoff, audit "
    "retention, observability, human review path, security review, deployment manifest, incident "
    "response plan, and measured pilot results."
)

GITHUB_ACTION_ADAPTERS = {
    "api_contract_change",
    "code_change_review",
    "database_migration_guardrail",
    "deployment_readiness",
    "infrastructure_change_guardrail",
}
LOCAL_DEMO_ADAPTERS = {
    "booking_purchase_guardrail",
    "calendar_scheduling",
    "email_send_guardrail",
    "file_operation_guardrail",
    "research_answer_grounding",
}
ENTERPRISE_PACK = {
    "access_permission_change",
    "code_change_review",
    "crm_support_reply",
    "data_export_guardrail",
    "deployment_readiness",
    "email_send_guardrail",
    "incident_response_update",
    "ticket_update_checker",
}
PERSONAL_PACK = {
    "booking_purchase_guardrail",
    "calendar_scheduling",
    "email_send_guardrail",
    "file_operation_guardrail",
    "meeting_summary_checker",
    "publication_check",
    "research_answer_grounding",
}
CIVIC_PACK = {
    "casework_response_checker",
    "foia_public_records_response_checker",
    "grant_application_review",
    "insurance_claim_triage",
    "policy_memo_grounding",
    "procurement_vendor_risk",
    "publication_check",
    "public_records_privacy_redaction",
}
STRICT_ROUTER_ADAPTERS = {
    "financial_advice_router",
    "legal_safety_router",
    "medical_safety_router",
}
ROLE_ADAPTERS = {
    "support": {
        "billing_reply",
        "crm_support_reply",
        "customer_success_renewal",
        "email_send_guardrail",
        "incident_response_update",
        "invoice_billing_reply",
        "ticket_update_checker",
    },
    "developer": {
        "api_contract_change",
        "code_change_review",
        "database_migration_guardrail",
        "deployment_readiness",
        "feature_flag_rollout",
        "infrastructure_change_guardrail",
        "model_evaluation_release",
    },
    "analyst": {
        "data_export_guardrail",
        "data_pipeline_change",
        "grant_application_review",
        "policy_memo_grounding",
        "procurement_vendor_risk",
        "product_requirements_checker",
        "publication_check",
        "research_answer_grounding",
    },
    "reviewer": {
        "access_permission_change",
        "financial_advice_router",
        "hiring_candidate_feedback",
        "legal_safety_router",
        "medical_safety_router",
        "performance_review",
        "public_records_privacy_redaction",
        "security_vulnerability_disclosure",
    },
    "citizen-services": {
        "casework_response_checker",
        "foia_public_records_response_checker",
        "grant_application_review",
        "insurance_claim_triage",
        "policy_memo_grounding",
        "public_records_privacy_redaction",
    },
}
FAMILY_LABELS = {
    "enterprise": "Enterprise",
    "personal_productivity": "Personal Productivity",
    "government_civic": "Government/Civic",
    "developer_tooling": "Developer Tooling",
}
READINESS_STATES = ("ready", "partial", "external_required", "not_packaged")
CATALOG_STATUSES = ("demo_adapter", "pilot_ready", "production_candidate")


def load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _adapter_path(entry, root=ROOT):
    value = pathlib.Path(str(entry.get("adapter_path", "")))
    return value if value.is_absolute() else root / value


def _unique_strings(values):
    seen = set()
    output = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            output.append(text)
    return output


def _constraint_summary(adapter):
    constraints = adapter.get("constraints", [])
    if not isinstance(constraints, list):
        constraints = []
    required_evidence = []
    hard_constraints = []
    layers = {}
    correction_routes = {}
    for item in constraints:
        if not isinstance(item, dict):
            continue
        layer = item.get("layer")
        if isinstance(layer, str) and layer:
            layers[layer] = layers.get(layer, 0) + 1
        if item.get("hard") is True and item.get("id"):
            hard_constraints.append(item["id"])
        correction = item.get("correction") if isinstance(item.get("correction"), dict) else {}
        route = correction.get("on_fail")
        if isinstance(route, str) and route:
            correction_routes[route] = correction_routes.get(route, 0) + 1
        grounding = item.get("grounding") if isinstance(item.get("grounding"), dict) else {}
        if grounding.get("required") is True:
            required_evidence.extend(grounding.get("sources", []) if isinstance(grounding.get("sources"), list) else [])
    return {
        "constraint_count": len(constraints),
        "hard_constraint_count": len(hard_constraints),
        "hard_constraints": hard_constraints,
        "layers": dict(sorted(layers.items())),
        "correction_routes": dict(sorted(correction_routes.items())),
        "required_evidence": _unique_strings(required_evidence),
    }


def _supported_surfaces(adapter_id):
    surfaces = [
        "CLI",
        "Python SDK",
        "HTTP bridge",
        "CLI adapter runner",
        "Workflow Contract",
        "Agent Event Contract",
        "HTTP bridge /workflow-check",
        "Web playground",
        "Published adapter gallery",
    ]
    if adapter_id in GITHUB_ACTION_ADAPTERS:
        surfaces.append("GitHub Action")
    if adapter_id in LOCAL_DEMO_ADAPTERS:
        surfaces.append("Local desktop/browser demo")
    if adapter_id in ENTERPRISE_PACK:
        surfaces.append("Enterprise starter/pilot pack")
    if adapter_id in PERSONAL_PACK:
        surfaces.append("Personal productivity starter/pilot pack")
    if adapter_id in CIVIC_PACK:
        surfaces.append("Government/civic starter/pilot pack")
    if adapter_id in STRICT_ROUTER_ADAPTERS:
        surfaces.append("Safety router skill")
    return surfaces


def _pack_membership(adapter_id):
    packs = []
    if adapter_id in ENTERPRISE_PACK:
        packs.append("enterprise")
    if adapter_id in PERSONAL_PACK:
        packs.append("personal_productivity")
    if adapter_id in CIVIC_PACK:
        packs.append("government_civic")
    if adapter_id in GITHUB_ACTION_ADAPTERS:
        packs.append("developer_tooling")
    return packs


def _role_membership(adapter_id):
    return [role for role, adapter_ids in sorted(ROLE_ADAPTERS.items()) if adapter_id in adapter_ids]


def adapter_families(adapter_id):
    """Return platform family memberships for an adapter id."""

    return _pack_membership(adapter_id)


def adapter_roles(adapter_id):
    """Return platform role memberships for an adapter id."""

    return _role_membership(adapter_id)


def _readiness_state(adapter_id, surfaces, packs, production_readiness):
    production_status = production_readiness.get("status")
    pilot_ready = bool(packs and any("starter/pilot pack" in surface for surface in surfaces))
    production_ready = production_status if production_status in READINESS_STATES else "external_required"
    return {
        "try": "ready" if "Web playground" in surfaces else "partial",
        "pilot": "ready" if pilot_ready else "not_packaged",
        "production": production_ready,
    }


def _entry_list(entry, field, fallback=None):
    value = entry.get(field)
    if isinstance(value, list) and value:
        return value
    return list(fallback or [])


def _adapter_card(entry, adapter, root=ROOT):
    adapter_id = entry.get("id")
    aix = adapter.get("aix") if isinstance(adapter.get("aix"), dict) else {}
    production_readiness = (
        adapter.get("production_readiness") if isinstance(adapter.get("production_readiness"), dict) else {}
    )
    constraints = _constraint_summary(adapter)
    domain = adapter.get("domain") if isinstance(adapter.get("domain"), dict) else {}
    failure_modes = adapter.get("failure_modes") if isinstance(adapter.get("failure_modes"), list) else []
    failure_mode_names = [item.get("name") for item in failure_modes if isinstance(item, dict)]
    evidence_requirements = entry.get("evidence_requirements", production_readiness.get("evidence_requirements", []))
    if not isinstance(evidence_requirements, list):
        evidence_requirements = []
    adapter_path = _adapter_path(entry, root=root)
    supported_surfaces = _entry_list(entry, "supported_surfaces", _supported_surfaces(adapter_id))
    declared_families = _entry_list(entry, "family", _pack_membership(adapter_id) or ["general"])
    packs = [item for item in declared_families if item != "general"]
    roles = _role_membership(adapter_id)
    readiness = _readiness_state(adapter_id, supported_surfaces, packs, production_readiness)
    catalog_status = entry.get("readiness") if entry.get("readiness") in CATALOG_STATUSES else "demo_adapter"
    production_status = (
        entry.get("production_status") if isinstance(entry.get("production_status"), dict) else {}
    )
    search_blob = " ".join(
        str(part)
        for part in [
            adapter_id,
            entry.get("title"),
            entry.get("workflow"),
            " ".join(entry.get("best_for", []) if isinstance(entry.get("best_for"), list) else []),
            " ".join(constraints["required_evidence"]),
            " ".join(failure_mode_names),
            " ".join(declared_families),
            " ".join(roles),
            catalog_status,
            " ".join(readiness.values()),
            aix.get("risk_tier"),
        ]
    ).lower()
    return {
        "id": adapter_id,
        "title": entry.get("title"),
        "product_line": entry.get("product_line"),
        "status": entry.get("status"),
        "workflow": entry.get("workflow") or domain.get("user_workflow"),
        "best_for": entry.get("best_for", []) if isinstance(entry.get("best_for"), list) else [],
        "adapter_path": adapter_path.relative_to(root).as_posix() if adapter_path.is_relative_to(root) else adapter_path.as_posix(),
        "readiness_status": catalog_status,
        "risk_tier": entry.get("risk_tier") or aix.get("risk_tier", "unspecified"),
        "aix": {
            "risk_tier": aix.get("risk_tier", "unspecified"),
            "beta": aix.get("beta"),
            "layer_weights": aix.get("layer_weights", {}) if isinstance(aix.get("layer_weights"), dict) else {},
            "thresholds": aix.get("thresholds", {}) if isinstance(aix.get("thresholds"), dict) else {},
        },
        "aix_tuning": entry.get("aix_tuning") if isinstance(entry.get("aix_tuning"), dict) else {
            "risk_tier": aix.get("risk_tier", "unspecified"),
            "beta": aix.get("beta"),
            "layer_weights": aix.get("layer_weights", {}) if isinstance(aix.get("layer_weights"), dict) else {},
            "thresholds": aix.get("thresholds", {}) if isinstance(aix.get("thresholds"), dict) else {},
        },
        "required_evidence": constraints["required_evidence"],
        "evidence_requirements": evidence_requirements,
        "verifier_behavior": entry.get("verifier_behavior", []) if isinstance(entry.get("verifier_behavior"), list) else [],
        "correction_policy_summary": entry.get("correction_policy_summary", [])
        if isinstance(entry.get("correction_policy_summary"), list)
        else [],
        "human_review_path": entry.get("human_review_path", []) if isinstance(entry.get("human_review_path"), list) else [],
        "human_review_requirements": entry.get("human_review_requirements", [])
        if isinstance(entry.get("human_review_requirements"), list)
        else [],
        "supported_surfaces": supported_surfaces,
        "packs": packs,
        "families": declared_families,
        "family_labels": [FAMILY_LABELS.get(family, family) for family in declared_families],
        "roles": roles,
        "readiness": readiness,
        "example_inputs": {
            "prompt": entry.get("prompt"),
            "bad_candidate": entry.get("bad_candidate"),
        },
        "example_outputs": {
            "expected": entry.get("expected", {}) if isinstance(entry.get("expected"), dict) else {},
            "expected_actions": entry.get("expected_actions", {})
            if isinstance(entry.get("expected_actions"), dict)
            else {},
            "copy_command": entry.get("copy_command"),
            "caveats": entry.get("caveats", []) if isinstance(entry.get("caveats"), list) else [],
        },
        "constraints": constraints,
        "failure_modes": _unique_strings(failure_mode_names),
        "production": {
            "status": production_status.get("level", catalog_status),
            "adapter_readiness": production_status.get("adapter_readiness", production_readiness.get("status")),
            "claim": production_status.get("claim"),
            "owner": production_readiness.get("owner"),
            "human_review_escalation": production_readiness.get("human_review_escalation", [])
            if isinstance(production_readiness.get("human_review_escalation"), list)
            else [],
        },
        "search_text": search_blob,
    }


def published_gallery(gallery_path=DEFAULT_GALLERY, root=ROOT):
    gallery = load_json(gallery_path)
    entries = gallery.get("adapters", []) if isinstance(gallery.get("adapters"), list) else []
    adapters = []
    risk_tier_counts = {}
    readiness_status_counts = {}
    surface_counts = {}
    pack_counts = {}
    role_counts = {}
    readiness_counts = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        adapter = load_json(_adapter_path(entry, root=root))
        card = _adapter_card(entry, adapter, root=root)
        adapters.append(card)
        risk_tier_counts[card["risk_tier"]] = risk_tier_counts.get(card["risk_tier"], 0) + 1
        readiness_status_counts[card["readiness_status"]] = readiness_status_counts.get(card["readiness_status"], 0) + 1
        for surface in card["supported_surfaces"]:
            surface_counts[surface] = surface_counts.get(surface, 0) + 1
        for pack in card["packs"]:
            pack_counts[pack] = pack_counts.get(pack, 0) + 1
        for role in card["roles"]:
            role_counts[role] = role_counts.get(role, 0) + 1
        for kind, state in card["readiness"].items():
            key = f"{kind}.{state}"
            readiness_counts[key] = readiness_counts.get(key, 0) + 1
    adapters.sort(key=lambda item: (item["risk_tier"], item["title"] or item["id"]))
    return {
        "published_gallery_version": PUBLISHED_GALLERY_VERSION,
        "source_gallery_version": gallery.get("version"),
        "description": "Searchable AANA adapter gallery for choosing guardrails by workflow, evidence, risk tier, surface, and AIx tuning.",
        "production_positioning": PRODUCTION_POSITIONING,
        "product_lines": gallery.get("product_lines", {}) if isinstance(gallery.get("product_lines"), dict) else {},
        "adapter_count": len(adapters),
        "risk_tier_counts": dict(sorted(risk_tier_counts.items())),
        "readiness_status_counts": dict(sorted(readiness_status_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "pack_counts": dict(sorted(pack_counts.items())),
        "family_counts": dict(sorted(pack_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "filters": {
            "risk_tiers": sorted(risk_tier_counts),
            "readiness_statuses": sorted(readiness_status_counts),
            "surfaces": sorted(surface_counts),
            "packs": sorted(pack_counts),
            "families": sorted(pack_counts),
            "roles": sorted(role_counts),
            "readiness": {
                "try": sorted({card["readiness"]["try"] for card in adapters}),
                "pilot": sorted({card["readiness"]["pilot"] for card in adapters}),
                "production": sorted({card["readiness"]["production"] for card in adapters}),
            },
        },
        "adapters": adapters,
    }


def write_published_gallery(output_path, gallery_path=DEFAULT_GALLERY, root=ROOT):
    payload = published_gallery(gallery_path=gallery_path, root=root)
    output = pathlib.Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
