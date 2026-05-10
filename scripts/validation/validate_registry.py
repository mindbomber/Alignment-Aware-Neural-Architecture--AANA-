#!/usr/bin/env python
"""Validate the unified AANA registry facade."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aana import canonical_ids, registry
from aana.adapters import FAMILY_IDS, load_adapter_families
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, load_bundles


def validate_registry() -> dict:
    issues: list[dict[str, str]] = []
    platform = registry.registry()
    if tuple(FAMILY_IDS) != platform.adapter_family_ids:
        issues.append({"level": "error", "path": "aana.adapters.FAMILY_IDS", "message": "Adapter facade must read family IDs from aana.registry."})
    if tuple(BUNDLE_IDS) != platform.bundle_ids:
        issues.append({"level": "error", "path": "aana.bundles.BUNDLE_IDS", "message": "Bundle facade must read bundle IDs from aana.registry."})
    if dict(BUNDLE_ALIASES) != platform.bundle_aliases:
        issues.append({"level": "error", "path": "aana.bundles.BUNDLE_ALIASES", "message": "Bundle aliases must read from aana.registry."})
    if set(load_adapter_families()) != set(platform.adapter_family_ids):
        issues.append({"level": "error", "path": "aana.adapters.load_adapter_families", "message": "Adapter loader drifted from aana.registry."})
    if set(load_bundles()) != set(platform.bundle_ids):
        issues.append({"level": "error", "path": "aana.bundles.load_bundles", "message": "Bundle loader drifted from aana.registry."})
    if canonical_ids.ACTION_ROUTES != platform.routes:
        issues.append({"level": "error", "path": "aana.canonical_ids.ACTION_ROUTES", "message": "Route constants must read from aana.registry."})
    if canonical_ids.ROUTE_TABLE != platform.route_table:
        issues.append({"level": "error", "path": "aana.canonical_ids.ROUTE_TABLE", "message": "Route table must read from aana.registry."})
    if not platform.dataset_entries():
        issues.append({"level": "error", "path": "hf_datasets", "message": "Registry must expose HF dataset entries."})
    if not platform.evidence_connectors.get("stubs"):
        issues.append({"level": "error", "path": "evidence_connectors.stubs", "message": "Registry must expose evidence connector stubs."})
    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "issues": issues,
        "summary": {
            "adapter_families": len(platform.adapter_family_ids),
            "bundles": len(platform.bundle_ids),
            "datasets": len(platform.dataset_entries()),
            "evidence_connectors": len(platform.evidence_connectors.get("stubs", [])),
            "routes": len(platform.routes),
            "aliases": {name: len(values) for name, values in platform.aliases.items()},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()
    report = validate_registry()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "fail"
        print(f"{status} -- registry surfaces={report['summary']}")
        for issue in report["issues"]:
            print(f"{issue['level']}: {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
