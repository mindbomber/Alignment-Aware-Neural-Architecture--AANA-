#!/usr/bin/env python
"""Validate the checked-in AANA adapter gallery."""

import argparse
import json
import pathlib
import sys
from urllib.parse import urlparse


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_adapter
import validate_adapter


REQUIRED_ENTRY_FIELDS = [
    "id",
    "title",
    "status",
    "adapter_path",
    "readiness",
    "family",
    "risk_tier",
    "evidence_requirements",
    "supported_surfaces",
    "production_status",
    "workflow",
    "best_for",
    "prompt",
    "bad_candidate",
    "expected",
    "copy_command",
    "caveats",
]
EXPECTED_FIELDS = [
    "candidate_gate",
    "gate_decision",
    "recommended_action",
    "failing_constraints",
    "aix_decision",
    "candidate_aix_decision",
]
CATALOG_READINESS = {"demo_adapter", "pilot_ready", "production_candidate"}
PRODUCTION_LEVELS = CATALOG_READINESS
RISK_TIERS = {"standard", "elevated", "high", "strict"}
REQUIRED_PUBLIC_SURFACES = {
    "Workflow Contract",
    "HTTP bridge /workflow-check",
    "Published adapter gallery",
}
SUPPORT_PRODUCT_LINE_ID = "support"
SUPPORT_PRODUCT_ADAPTERS = {
    "support_reply",
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "invoice_billing_reply",
}
SUPPORT_LATER_ADAPTERS = {
    "refunds",
    "account_closure",
    "chargeback",
    "cancellation",
    "escalation",
    "retention_deletion_request",
}
REQUIRED_SUPPORT_SURFACES = {
    "CLI",
    "Python SDK",
    "HTTP bridge",
    "Workflow Contract",
    "Agent Event Contract",
}
SUPPORT_ENTRY_FIELDS = [
    "product_line",
    "expected_actions",
    "aix_tuning",
    "verifier_behavior",
    "correction_policy_summary",
    "human_review_path",
    "human_review_requirements",
]
SUPPORT_CATALOG_CONTRACT_FIELDS = {
    "readiness",
    "family",
    "risk_tier",
    "evidence_requirements",
    "supported_surfaces",
    "expected_actions",
    "aix_tuning",
    "caveats",
    "production_status",
    "docs_links",
    "copy_command",
    "human_review_requirements",
}
SUPPORT_ALLOWED_ACTIONS = {"accept", "revise", "retrieve", "ask", "defer", "refuse"}
COMPLETENESS_FIELDS = [
    "id",
    "title",
    "status",
    "adapter_path",
    "readiness",
    "family",
    "risk_tier",
    "evidence_requirements",
    "supported_surfaces",
    "production_status",
    "workflow",
    "best_for",
    "prompt",
    "bad_candidate",
    "expected",
    "copy_command",
    "caveats",
]
MIN_CATALOG_COMPLETENESS_SCORE = 0.95


def add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def has_text(value):
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value):
    return isinstance(value, list) and bool(value)


def load_gallery(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        gallery = json.load(handle)
    if not isinstance(gallery, dict):
        raise ValueError("Gallery file must contain a JSON object.")
    return gallery


def _is_docs_link(value):
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return True
    path = pathlib.Path(value)
    return bool(path.parts) and path.parts[0] in {"docs", "examples", "web", ".github"}


def _link_exists(value):
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return True
    return (ROOT / value).exists()


def _entry_docs_links(entry):
    links = []
    for field in ("docs", "docs_links", "documentation", "documentation_links"):
        value = entry.get(field)
        if isinstance(value, str):
            links.append(value)
        elif isinstance(value, list):
            links.extend(item for item in value if isinstance(item, str))
    for value in entry.get("supported_surfaces", []) if isinstance(entry.get("supported_surfaces"), list) else []:
        if _is_docs_link(value):
            links.append(value)
    return links


def _entry_completeness(entry):
    present = []
    missing = []
    weak = []
    for field in COMPLETENESS_FIELDS:
        value = entry.get(field)
        ok = has_text(value) or nonempty_list(value) or isinstance(value, dict)
        if ok:
            present.append(field)
        else:
            missing.append(field)
    if entry.get("product_line") == SUPPORT_PRODUCT_LINE_ID:
        for field in ("expected_actions", "human_review_requirements"):
            value = entry.get(field)
            ok = has_text(value) or nonempty_list(value) or isinstance(value, dict)
            if ok:
                present.append(field)
            else:
                missing.append(field)
    expected = entry.get("expected") if isinstance(entry.get("expected"), dict) else {}
    for field in EXPECTED_FIELDS:
        if has_text(expected.get(field)) or nonempty_list(expected.get(field)):
            present.append(f"expected.{field}")
        else:
            missing.append(f"expected.{field}")
    production_status = entry.get("production_status") if isinstance(entry.get("production_status"), dict) else {}
    for field in ("level", "adapter_readiness", "claim"):
        if has_text(production_status.get(field)):
            present.append(f"production_status.{field}")
        else:
            missing.append(f"production_status.{field}")
    if len(entry.get("caveats", [])) < 2:
        weak.append("caveats")
    if len(entry.get("evidence_requirements", [])) < 1:
        weak.append("evidence_requirements")
    total = len(present) + len(missing) + len(weak)
    score = round(len(present) / total, 4) if total else 0.0
    return {
        "id": entry.get("id"),
        "score": score,
        "present": len(present),
        "missing": missing,
        "weak": weak,
    }


def validate_entry_shape(entry, index, issues):
    base = f"adapters[{index}]"
    if not isinstance(entry, dict):
        add_issue(issues, "error", base, "Adapter gallery entry must be an object.")
        return

    for field in REQUIRED_ENTRY_FIELDS:
        if field not in entry:
            add_issue(issues, "error", f"{base}.{field}", "Required field is missing.")

    for field in ["id", "title", "status", "adapter_path", "readiness", "risk_tier", "workflow", "prompt", "bad_candidate", "copy_command"]:
        if field in entry and not has_text(entry.get(field)):
            add_issue(issues, "error", f"{base}.{field}", "Field must be a non-empty string.")

    for field in ["family", "evidence_requirements", "supported_surfaces", "best_for", "caveats"]:
        if field in entry and not nonempty_list(entry.get(field)):
            add_issue(issues, "error", f"{base}.{field}", "Field must be a non-empty list.")

    docs_links = _entry_docs_links(entry)
    if not docs_links:
        add_issue(issues, "error", f"{base}.docs_links", "Catalog entry must include at least one docs link.")
    for link in docs_links:
        if not _link_exists(link):
            add_issue(issues, "error", f"{base}.docs_links", f"Docs link does not resolve: {link}.")

    if entry.get("readiness") not in CATALOG_READINESS:
        add_issue(issues, "error", f"{base}.readiness", f"Readiness must be one of {sorted(CATALOG_READINESS)}.")

    if entry.get("risk_tier") not in RISK_TIERS:
        add_issue(issues, "error", f"{base}.risk_tier", f"Risk tier must be one of {sorted(RISK_TIERS)}.")

    surfaces = set(entry.get("supported_surfaces", []) if isinstance(entry.get("supported_surfaces"), list) else [])
    missing_surfaces = REQUIRED_PUBLIC_SURFACES - surfaces
    if missing_surfaces:
        add_issue(
            issues,
            "error",
            f"{base}.supported_surfaces",
            f"Supported surfaces must include public catalog/runtime surfaces: {sorted(missing_surfaces)}.",
        )

    production_status = entry.get("production_status")
    if not isinstance(production_status, dict):
        add_issue(issues, "error", f"{base}.production_status", "Production status must be an object.")
    else:
        if production_status.get("level") not in PRODUCTION_LEVELS:
            add_issue(
                issues,
                "error",
                f"{base}.production_status.level",
                f"Production status level must be one of {sorted(PRODUCTION_LEVELS)}.",
            )
        for field in ["adapter_readiness", "claim"]:
            if not has_text(production_status.get(field)):
                add_issue(issues, "error", f"{base}.production_status.{field}", "Field must be a non-empty string.")

    expected = entry.get("expected", {})
    if not isinstance(expected, dict):
        add_issue(issues, "error", f"{base}.expected", "Expected result must be an object.")
        return

    for field in EXPECTED_FIELDS:
        if field not in expected:
            add_issue(issues, "error", f"{base}.expected.{field}", "Required expected field is missing.")

    for field in ["candidate_gate", "gate_decision", "recommended_action", "aix_decision", "candidate_aix_decision"]:
        if field in expected and not has_text(expected.get(field)):
            add_issue(issues, "error", f"{base}.expected.{field}", "Expected field must be a non-empty string.")

    if "failing_constraints" in expected and not nonempty_list(expected.get("failing_constraints")):
        add_issue(issues, "error", f"{base}.expected.failing_constraints", "Expected failing constraints must be a non-empty list.")


def validate_support_product_line(gallery, entries, issues):
    product_lines = gallery.get("product_lines")
    if not isinstance(product_lines, dict):
        add_issue(issues, "error", "product_lines", "Gallery must define product_lines for productized adapter lines.")
        return

    support = product_lines.get(SUPPORT_PRODUCT_LINE_ID)
    if not isinstance(support, dict):
        add_issue(issues, "error", "product_lines.support", "Gallery must define the support adapter product line.")
        return

    adapter_ids = set(support.get("adapter_ids", []) if isinstance(support.get("adapter_ids"), list) else [])
    missing_adapters = SUPPORT_PRODUCT_ADAPTERS - adapter_ids
    if missing_adapters:
        add_issue(
            issues,
            "error",
            "product_lines.support.adapter_ids",
            f"Support product line is missing required adapters: {sorted(missing_adapters)}.",
        )

    later_adapters = set(support.get("later_adapters", []) if isinstance(support.get("later_adapters"), list) else [])
    missing_later = SUPPORT_LATER_ADAPTERS - later_adapters
    if missing_later:
        add_issue(
            issues,
            "error",
            "product_lines.support.later_adapters",
            f"Support product line is missing later-roadmap adapters: {sorted(missing_later)}.",
        )

    for field in ("title", "boundary", "primary_goal"):
        if not has_text(support.get(field)):
            add_issue(issues, "error", f"product_lines.support.{field}", "Field must be a non-empty string.")
    if not has_text(support.get("source_of_truth")):
        add_issue(
            issues,
            "error",
            "product_lines.support.source_of_truth",
            "Support product line must declare the catalog source of truth.",
        )
    catalog_contract = set(
        support.get("catalog_contract", []) if isinstance(support.get("catalog_contract"), list) else []
    )
    missing_contract_fields = SUPPORT_CATALOG_CONTRACT_FIELDS - catalog_contract
    if missing_contract_fields:
        add_issue(
            issues,
            "error",
            "product_lines.support.catalog_contract",
            f"Support catalog contract is missing required fields: {sorted(missing_contract_fields)}.",
        )

    by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    for adapter_id in sorted(SUPPORT_PRODUCT_ADAPTERS):
        entry = by_id.get(adapter_id)
        if not entry:
            add_issue(issues, "error", f"product_lines.support.adapter_ids.{adapter_id}", "Support adapter is not present in the gallery.")
            continue
        base = f"adapters.{adapter_id}"
        if entry.get("product_line") != SUPPORT_PRODUCT_LINE_ID:
            add_issue(issues, "error", f"{base}.product_line", "Support adapters must declare product_line='support'.")
        for field in SUPPORT_ENTRY_FIELDS:
            value = entry.get(field)
            if not (has_text(value) or nonempty_list(value) or isinstance(value, dict)):
                add_issue(issues, "error", f"{base}.{field}", "Support product entries must declare this field.")
        expected = entry.get("expected") if isinstance(entry.get("expected"), dict) else {}
        expected_actions = entry.get("expected_actions") if isinstance(entry.get("expected_actions"), dict) else {}
        allowed_actions = set(
            expected_actions.get("allowed_actions", [])
            if isinstance(expected_actions.get("allowed_actions"), list)
            else []
        )
        if allowed_actions != SUPPORT_ALLOWED_ACTIONS:
            add_issue(
                issues,
                "error",
                f"{base}.expected_actions.allowed_actions",
                f"Support expected actions must declare exactly {sorted(SUPPORT_ALLOWED_ACTIONS)}.",
            )
        expected_action_pairs = {
            "golden_candidate_gate": "candidate_gate",
            "golden_recommended_action": "recommended_action",
            "golden_candidate_aix_decision": "candidate_aix_decision",
        }
        for expected_action_field, expected_field in expected_action_pairs.items():
            if expected_actions.get(expected_action_field) != expected.get(expected_field):
                add_issue(
                    issues,
                    "error",
                    f"{base}.expected_actions.{expected_action_field}",
                    f"Support expected action must match expected.{expected_field}.",
                )
        aix_tuning = entry.get("aix_tuning") if isinstance(entry.get("aix_tuning"), dict) else {}
        if aix_tuning.get("risk_tier") != entry.get("risk_tier"):
            add_issue(
                issues,
                "error",
                f"{base}.aix_tuning.risk_tier",
                "Support AIx tuning risk tier must match gallery risk_tier.",
            )
        surfaces = set(entry.get("supported_surfaces", []) if isinstance(entry.get("supported_surfaces"), list) else [])
        missing_surfaces = REQUIRED_SUPPORT_SURFACES - surfaces
        if missing_surfaces:
            add_issue(
                issues,
                "error",
                f"{base}.supported_surfaces",
                f"Support adapters must include product runtime surfaces: {sorted(missing_surfaces)}.",
            )
        production_status = entry.get("production_status") if isinstance(entry.get("production_status"), dict) else {}
        if not has_text(production_status.get("claim")):
            add_issue(issues, "error", f"{base}.production_status.claim", "Support adapters must declare a conservative production claim.")


def validate_gallery(gallery, run_examples=False):
    issues = []
    completeness_items = []

    if not has_text(gallery.get("version")):
        add_issue(issues, "error", "version", "Gallery version must be a non-empty string.")
    if not has_text(gallery.get("description")):
        add_issue(issues, "error", "description", "Gallery description must be a non-empty string.")

    entries = gallery.get("adapters", [])
    if not nonempty_list(entries):
        add_issue(issues, "error", "adapters", "Gallery must contain at least one adapter entry.")
        entries = []

    seen_ids = set()
    checked = []
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        validate_entry_shape(entry, index, issues)
        if not isinstance(entry, dict):
            continue
        completeness_items.append(_entry_completeness(entry))

        entry_id = entry.get("id")
        if entry_id in seen_ids:
            add_issue(issues, "error", f"adapters[{index}].id", f"Duplicate gallery id: {entry_id}.")
        seen_ids.add(entry_id)

        adapter_path = ROOT / str(entry.get("adapter_path", ""))
        if not adapter_path.exists():
            add_issue(issues, "error", f"adapters[{index}].adapter_path", f"Adapter file does not exist: {entry.get('adapter_path')}.")
            continue

        try:
            adapter = validate_adapter.load_adapter(adapter_path)
            adapter_report = validate_adapter.validate_adapter(adapter)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add_issue(issues, "error", f"adapters[{index}].adapter_path", f"Adapter could not be loaded: {exc}.")
            continue

        if not adapter_report["valid"]:
            add_issue(issues, "error", f"adapters[{index}].adapter_path", "Referenced adapter does not pass adapter validation.")

        adapter_aix = adapter.get("aix") if isinstance(adapter.get("aix"), dict) else {}
        if entry.get("risk_tier") != adapter_aix.get("risk_tier"):
            add_issue(
                issues,
                "error",
                f"adapters[{index}].risk_tier",
                f"Gallery risk_tier must match adapter AIx risk_tier {adapter_aix.get('risk_tier')!r}.",
            )

        production_readiness = (
            adapter.get("production_readiness")
            if isinstance(adapter.get("production_readiness"), dict)
            else {}
        )
        production_status = entry.get("production_status") if isinstance(entry.get("production_status"), dict) else {}
        if production_status.get("adapter_readiness") != production_readiness.get("status"):
            add_issue(
                issues,
                "error",
                f"adapters[{index}].production_status.adapter_readiness",
                "Gallery production_status.adapter_readiness must match the adapter production_readiness.status.",
            )

        declared_evidence = set(entry.get("evidence_requirements", []))
        adapter_evidence = set(
            production_readiness.get("evidence_requirements", [])
            if isinstance(production_readiness.get("evidence_requirements"), list)
            else []
        )
        missing_evidence = adapter_evidence - declared_evidence
        if missing_evidence:
            add_issue(
                issues,
                "error",
                f"adapters[{index}].evidence_requirements",
                f"Gallery evidence requirements must include adapter evidence requirements: {sorted(missing_evidence)}.",
            )

        if run_examples and entry.get("status") == "executable":
            result = run_adapter.run_adapter(adapter, entry.get("prompt", ""), entry.get("bad_candidate", ""))
            expected = entry.get("expected", {})
            for key in ["candidate_gate", "gate_decision", "recommended_action"]:
                if result.get(key) != expected.get(key):
                    add_issue(
                        issues,
                        "error",
                        f"adapters[{index}].expected.{key}",
                        f"Expected {expected.get(key)!r}, got {result.get(key)!r}.",
                    )

            aix_decision = result.get("aix", {}).get("decision")
            if aix_decision != expected.get("aix_decision"):
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.aix_decision",
                    f"Expected {expected.get('aix_decision')!r}, got {aix_decision!r}.",
                )

            candidate_aix_decision = result.get("candidate_aix", {}).get("decision")
            if candidate_aix_decision != expected.get("candidate_aix_decision"):
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.candidate_aix_decision",
                    f"Expected {expected.get('candidate_aix_decision')!r}, got {candidate_aix_decision!r}.",
                )

            failed_constraints = {
                item.get("id")
                for item in result.get("constraint_results", [])
                if item.get("status") == "fail"
            }
            if failed_constraints:
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected",
                    f"Final gated result still has failing constraints: {sorted(failed_constraints)}.",
                )

            candidate_failures = set()
            for violation in result.get("candidate_tool_report", {}).get("violations", []):
                candidate_failures.update(
                    run_adapter.violation_constraint_ids(adapter, violation.get("code"))
                )
            expected_failures = set(expected.get("failing_constraints", []))
            missing_failures = expected_failures - candidate_failures
            if missing_failures:
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.failing_constraints",
                    f"Bad candidate did not trigger expected constraints: {sorted(missing_failures)}.",
                )

            checked.append(
                {
                    "id": entry_id,
                    "gate_decision": result.get("gate_decision"),
                    "recommended_action": result.get("recommended_action"),
                    "aix_decision": aix_decision,
                }
            )

    validate_support_product_line(gallery, entries if isinstance(entries, list) else [], issues)

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    average_score = (
        round(sum(item["score"] for item in completeness_items) / len(completeness_items), 4)
        if completeness_items
        else 0.0
    )
    weak_entries = [item for item in completeness_items if item["score"] < MIN_CATALOG_COMPLETENESS_SCORE]
    completeness = {
        "score": average_score,
        "minimum_required": MIN_CATALOG_COMPLETENESS_SCORE,
        "entry_count": len(completeness_items),
        "weak_entry_count": len(weak_entries),
        "weak_entries": weak_entries,
        "readiness_counts": {},
    }
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            readiness = entry.get("readiness")
            completeness["readiness_counts"][readiness] = completeness["readiness_counts"].get(readiness, 0) + 1
    if average_score < MIN_CATALOG_COMPLETENESS_SCORE or weak_entries:
        errors += 1
        add_issue(
            issues,
            "error",
            "catalog_completeness",
            f"Catalog completeness score {average_score} is below required {MIN_CATALOG_COMPLETENESS_SCORE}.",
        )
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "checked_examples": checked,
        "catalog_completeness": completeness,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the AANA adapter gallery.")
    parser.add_argument("--gallery", default="examples/adapter_gallery.json", help="Path to adapter gallery JSON.")
    parser.add_argument("--run-examples", action="store_true", help="Run executable examples and compare expected gate behavior.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    gallery = load_gallery(args.gallery)
    report = validate_gallery(gallery, run_examples=args.run_examples)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter gallery is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        if report["checked_examples"]:
            print("Checked examples:")
            for item in report["checked_examples"]:
                print(f"- {item['id']}: gate={item['gate_decision']} action={item['recommended_action']} aix={item.get('aix_decision')}")
        completeness = report.get("catalog_completeness", {})
        if completeness:
            print(
                f"Catalog completeness: {completeness.get('score')} "
                f"(weak entries: {completeness.get('weak_entry_count')})"
            )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adapter gallery validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
