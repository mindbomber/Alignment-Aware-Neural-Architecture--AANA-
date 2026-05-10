#!/usr/bin/env python
"""Run AANA starter pilot kits with synthetic workflow data."""

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_INDEX = ROOT / "examples" / "starter_pilot_kits" / "index.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_OUTPUT_ROOT = ROOT / "eval_outputs" / "starter_pilot_kits"
WORKFLOW_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]
KIT_ALIASES = {"civic_government": "government_civic"}


class StarterPilotKitError(RuntimeError):
    pass


def load_json(path):
    path = pathlib.Path(path)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise StarterPilotKitError(f"{path} must contain a JSON object.")
    return data


def write_json(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_index(path):
    index = load_json(path)
    kits = index.get("kits")
    if not isinstance(kits, list) or not kits:
        raise StarterPilotKitError("Starter pilot kit index must include a non-empty kits list.")
    for kit in kits:
        if not isinstance(kit, dict) or not kit.get("id") or not kit.get("path"):
            raise StarterPilotKitError("Each starter pilot kit index entry must include id and path.")
    return index


def selected_kits(index, selections):
    requested = {KIT_ALIASES.get(selection, selection) for selection in (selections or ["all"])}
    kits = index["kits"]
    if "all" not in requested:
        kits = [kit for kit in kits if kit["id"] in requested]
    if not kits:
        raise StarterPilotKitError("No starter pilot kits matched the requested selection.")
    missing = requested - {"all"} - {kit["id"] for kit in index["kits"]}
    if missing:
        raise StarterPilotKitError("Unknown starter pilot kit id(s): " + ", ".join(sorted(missing)))
    return kits


def load_kit_bundle(kit_path):
    kit_path = pathlib.Path(kit_path)
    bundle = {
        "path": kit_path,
        "manifest": load_json(kit_path / "manifest.json"),
        "adapter_config": load_json(kit_path / "adapter_config.json"),
        "synthetic_data": load_json(kit_path / "synthetic_data.json"),
        "workflows": load_json(kit_path / "workflows.json"),
        "expected_outcomes": load_json(kit_path / "expected_outcomes.json"),
    }
    workflows = bundle["workflows"].get("workflows")
    records = bundle["synthetic_data"].get("records")
    if not isinstance(workflows, list) or not workflows:
        raise StarterPilotKitError(f"{kit_path} workflows.json must include a non-empty workflows list.")
    if not isinstance(records, dict) or not records:
        raise StarterPilotKitError(f"{kit_path} synthetic_data.json must include a non-empty records object.")
    return bundle


def find_gallery_entry(gallery, adapter_id):
    for entry in gallery.get("adapters", []):
        if entry.get("id") == adapter_id:
            return entry
    raise StarterPilotKitError(f"Unknown adapter id in starter pilot kit: {adapter_id}")


def evidence_for_refs(synthetic_data, refs, workflow_id):
    records = synthetic_data.get("records", {})
    evidence = []
    for ref in refs or []:
        item = records.get(ref)
        if not isinstance(item, dict):
            raise StarterPilotKitError(f"Workflow {workflow_id} references unknown synthetic evidence: {ref}")
        evidence.append({**item, "metadata": {"synthetic_record_id": ref}})
    return evidence


def expected_for_workflow(expected_outcomes, workflow_id):
    expected = dict(expected_outcomes.get("default_expected", {}))
    per_workflow = expected_outcomes.get("per_workflow", {})
    if isinstance(per_workflow, dict) and isinstance(per_workflow.get(workflow_id), dict):
        expected.update(per_workflow[workflow_id])
    return expected


def materialize_workflow(kit_id, workflow, gallery_entry, evidence, expected):
    workflow_id = workflow["workflow_id"]
    return {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow_id,
        "adapter": workflow["adapter_id"],
        "request": workflow.get("request") or gallery_entry.get("prompt", ""),
        "candidate": workflow.get("candidate") or gallery_entry.get("bad_candidate", ""),
        "evidence": evidence,
        "constraints": workflow.get("constraints", []),
        "allowed_actions": workflow.get("allowed_actions", WORKFLOW_ALLOWED_ACTIONS),
        "metadata": {
            "starter_kit": kit_id,
            "scenario": workflow_id,
            "adapter_family": workflow.get("adapter_family"),
            "data_basis": "synthetic",
            "gallery_demo": bool(workflow.get("gallery_demo")),
            "evidence_refs": list(workflow.get("evidence_refs", [])),
            "expected_candidate_gate": expected.get("candidate_gate"),
            "expected_gate_decision": expected.get("gate_decision"),
            "expected_recommended_action": expected.get("recommended_action"),
            "expected_aix_decision": expected.get("aix_decision"),
            "expected_candidate_aix_decision": expected.get("candidate_aix_decision"),
        },
    }


def expectation_checks(expected, result):
    checks = {
        "candidate_gate": expected.get("candidate_gate") is None or result.get("candidate_gate") == expected.get("candidate_gate"),
        "gate_decision": expected.get("gate_decision") is None or result.get("gate_decision") == expected.get("gate_decision"),
        "recommended_action": expected.get("recommended_action") is None
        or result.get("recommended_action") == expected.get("recommended_action"),
        "aix_decision": expected.get("aix_decision") is None
        or result.get("aix", {}).get("decision") == expected.get("aix_decision"),
        "candidate_aix_decision": expected.get("candidate_aix_decision") is None
        or result.get("candidate_aix", {}).get("decision") == expected.get("candidate_aix_decision"),
    }
    return checks, all(checks.values())


def metric_value(metrics, key):
    if key in metrics:
        return metrics[key]
    value = metrics
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def minimum_metric_checks(metrics_export, minimum_metrics):
    metrics = metrics_export.get("metrics", {})
    checks = {}
    for key, minimum in (minimum_metrics or {}).items():
        actual = metric_value(metrics, key)
        checks[key] = {
            "actual": actual,
            "minimum": minimum,
            "passed": isinstance(actual, (int, float)) and actual >= minimum,
        }
    return checks, all(item["passed"] for item in checks.values())


def prepare_output_dir(output_root, kit_id, append=False):
    output_dir = pathlib.Path(output_root) / kit_id
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_log = output_dir / "audit.jsonl"
    if append:
        audit_log.touch(exist_ok=True)
    else:
        audit_log.write_text("", encoding="utf-8")
    return {
        "dir": output_dir,
        "audit_log": audit_log,
        "metrics": output_dir / "metrics.json",
        "report_json": output_dir / "report.json",
        "report_md": output_dir / "report.md",
        "materialized_workflows": output_dir / "materialized_workflows.json",
    }


def scenario_report(workflow, result, expected, checks, passed):
    aix = result.get("aix", {}) if isinstance(result.get("aix"), dict) else {}
    candidate_aix = result.get("candidate_aix", {}) if isinstance(result.get("candidate_aix"), dict) else {}
    return {
        "workflow_id": workflow.get("workflow_id"),
        "adapter_id": workflow.get("adapter"),
        "passed": passed,
        "expected": expected,
        "expectation_checks": checks,
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "candidate_aix_score": candidate_aix.get("score"),
        "candidate_aix_decision": candidate_aix.get("decision"),
        "violations": [violation.get("code") for violation in result.get("violations", [])],
    }


def render_markdown_report(report):
    summary = report["summary"]
    metrics = report["metrics"].get("metrics", {})
    lines = [
        f"# AANA Starter Pilot Kit: {report['title']}",
        "",
        f"Status: {'PASS' if report['valid'] else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Kit: `{report['kit_id']}`",
        f"- Workflows: {summary['workflows']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Audit records: {summary['audit_records']}",
        f"- Audit log: `{summary['audit_log']}`",
        f"- Metrics JSON: `{summary['metrics_output']}`",
        f"- Materialized workflows: `{summary['materialized_workflows']}`",
        "",
        "## Metrics",
        "",
    ]
    for key in [
        "audit_records_total",
        "gate_decision_count",
        "recommended_action_count",
        "adapter_check_count",
        "aix_score_average",
        "aix_score_min",
        "aix_score_max",
        "aix_decision_count",
        "aix_hard_blocker_count",
    ]:
        if key in metrics:
            lines.append(f"- `{key}`: {metrics[key]}")
    lines.extend(
        [
            "",
            "## Workflows",
            "",
            "| Workflow | Adapter | Status | Gate | Action | Candidate Gate | AIx | Candidate AIx | Violations |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for scenario in report["scenarios"]:
        status = "PASS" if scenario["passed"] else "FAIL"
        lines.append(
            "| {workflow} | {adapter} | {status} | {gate} | {action} | {candidate_gate} | {aix} | {candidate_aix} | {violations} |".format(
                workflow=scenario["workflow_id"],
                adapter=scenario["adapter_id"],
                status=status,
                gate=scenario.get("gate_decision", ""),
                action=scenario.get("recommended_action", ""),
                candidate_gate=scenario.get("candidate_gate", ""),
                aix=scenario.get("aix_decision", ""),
                candidate_aix=scenario.get("candidate_aix_decision", ""),
                violations=", ".join(scenario.get("violations", [])),
            )
        )
    return "\n".join(lines) + "\n"


def run_kit(kit_entry, args):
    kit_id = kit_entry["id"]
    kit_path = ROOT / kit_entry["path"]
    bundle = load_kit_bundle(kit_path)
    gallery = agent_api.load_gallery(args.gallery)
    outputs = prepare_output_dir(args.output_root, kit_id, append=args.append)

    materialized = []
    scenarios = []
    for workflow_spec in bundle["workflows"]["workflows"]:
        workflow_id = workflow_spec.get("workflow_id")
        adapter_id = workflow_spec.get("adapter_id")
        if not workflow_id or not adapter_id:
            raise StarterPilotKitError(f"{kit_id} workflow is missing workflow_id or adapter_id.")
        gallery_entry = find_gallery_entry(gallery, adapter_id)
        expected = expected_for_workflow(bundle["expected_outcomes"], workflow_id)
        evidence = evidence_for_refs(bundle["synthetic_data"], workflow_spec.get("evidence_refs", []), workflow_id)
        workflow = materialize_workflow(kit_id, workflow_spec, gallery_entry, evidence, expected)
        materialized.append(workflow)

        validation = agent_api.validate_workflow_request(workflow)
        if not validation["valid"]:
            messages = "; ".join(issue["message"] for issue in validation["issues"] if issue["level"] == "error")
            raise StarterPilotKitError(f"Workflow {workflow_id} is invalid: {messages}")

        result = agent_api.check_workflow_request(workflow, gallery_path=args.gallery)
        agent_api.append_audit_record(outputs["audit_log"], agent_api.audit_workflow_check(workflow, result))
        checks, passed = expectation_checks(expected, result)
        scenarios.append(scenario_report(workflow, result, expected, checks, passed))

    batch = {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "batch_id": f"{kit_id}-starter-pilot-kit",
        "requests": materialized,
    }
    write_json(outputs["materialized_workflows"], batch)

    metrics = agent_api.export_audit_metrics_file(outputs["audit_log"], output_path=outputs["metrics"])
    metric_checks, metrics_passed = minimum_metric_checks(metrics, bundle["expected_outcomes"].get("minimum_metrics", {}))
    failed = [scenario for scenario in scenarios if not scenario["passed"]]
    manifest = bundle["manifest"]
    report = {
        "starter_pilot_kit_report_version": "0.1",
        "kit_id": kit_id,
        "title": manifest.get("title", kit_id),
        "valid": not failed and metrics_passed,
        "summary": {
            "workflows": len(scenarios),
            "passed": len(scenarios) - len(failed),
            "failed": len(failed),
            "audit_records": metrics["record_count"],
            "audit_log": str(outputs["audit_log"]),
            "metrics_output": str(outputs["metrics"]),
            "materialized_workflows": str(outputs["materialized_workflows"]),
            "markdown_report": str(outputs["report_md"]),
        },
        "manifest": manifest,
        "adapter_config": bundle["adapter_config"],
        "minimum_metric_checks": metric_checks,
        "scenarios": scenarios,
        "metrics": metrics,
    }
    write_json(outputs["report_json"], report)
    outputs["report_md"].write_text(render_markdown_report(report), encoding="utf-8")
    return report


def run_selected(args):
    index = load_index(args.index)
    reports = [run_kit(kit_entry, args) for kit_entry in selected_kits(index, args.kit)]
    failed = [report for report in reports if not report["valid"]]
    return {
        "starter_pilot_kits_report_version": "0.1",
        "valid": not failed,
        "summary": {
            "kits": len(reports),
            "passed": len(reports) - len(failed),
            "failed": len(failed),
            "workflows": sum(report["summary"]["workflows"] for report in reports),
            "audit_records": sum(report["summary"]["audit_records"] for report in reports),
            "output_root": str(pathlib.Path(args.output_root)),
        },
        "kits": reports,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AANA starter pilot kits with synthetic workflow data.")
    parser.add_argument("--kit", action="append", default=None, help="Kit id to run. Repeat as needed, or use all.")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Starter pilot kit index JSON.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory for generated audit, metrics, and reports.")
    parser.add_argument("--append", action="store_true", help="Append to existing kit audit logs instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print the combined JSON report.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        report = run_selected(args)
    except (StarterPilotKitError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA starter pilot kits: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["valid"] else "FAIL"
        summary = report["summary"]
        print(f"AANA starter pilot kits: {status}")
        print(f"- Kits: {summary['kits']}")
        print(f"- Workflows: {summary['workflows']}")
        print(f"- Audit records: {summary['audit_records']}")
        print(f"- Output root: {summary['output_root']}")
        for kit in report["kits"]:
            kit_summary = kit["summary"]
            print(f"- {kit['kit_id']}: {kit_summary['passed']}/{kit_summary['workflows']} workflows passed")
            print(f"  report: {kit_summary['markdown_report']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
