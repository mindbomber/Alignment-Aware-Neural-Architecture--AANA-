import aana
from aana import canonical_ids, registry
from aana.adapters import FAMILY_IDS, load_adapter_families
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, bundle_adapter_aliases, load_bundles


def test_unified_registry_loads_core_platform_surfaces():
    platform = registry.registry()

    assert set(platform.adapter_family_ids) == {
        "privacy_pii",
        "grounded_qa",
        "agent_tool_use",
        "governance_compliance",
        "security_devops",
        "domain_risk",
    }
    assert set(platform.bundle_ids) == {"enterprise", "enterprise_ops_pilot", "personal_productivity", "government_civic"}
    assert platform.routes == ("accept", "revise", "retrieve", "ask", "defer", "refuse")
    assert platform.route_table["accept"]["execution_allowed"] is True
    assert all(not platform.route_table[route]["execution_allowed"] for route in platform.routes if route != "accept")
    assert platform.dataset_entries()
    assert "crm_support" in platform.evidence_connectors["core"]
    assert "civic_source_registry" in platform.evidence_connectors["government_civic"]


def test_legacy_adapter_and_bundle_facades_read_from_registry():
    platform = registry.registry()

    assert tuple(FAMILY_IDS) == platform.adapter_family_ids
    assert tuple(BUNDLE_IDS) == platform.bundle_ids
    assert dict(BUNDLE_ALIASES) == platform.bundle_aliases
    assert set(load_adapter_families()) == set(platform.adapter_family_ids)
    assert set(load_bundles()) == set(platform.bundle_ids)
    assert bundle_adapter_aliases("enterprise") == platform.bundle_adapter_aliases("enterprise")


def test_canonical_ids_and_public_aana_exports_read_registry_routes():
    platform = registry.registry()

    assert canonical_ids.ACTION_ROUTES == platform.routes
    assert canonical_ids.ROUTE_TABLE == platform.route_table
    assert aana.platform_registry().routes == platform.routes
    assert aana.ROUTE_TABLE == platform.route_table
