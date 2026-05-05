#!/usr/bin/env python
"""Run the AANA Pilot Evaluation Kit and write audit, metrics, and reports."""

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_KIT = ROOT / "examples" / "pilot_evaluation_kit.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "pilot_eval" / "aana-pilot-eval.jsonl"
DEFAULT_REPORT = ROOT / "eval_outputs" / "pilot_eval" / "aana-pilot-eval-report.md"
DEFAULT_JSON_REPORT = ROOT / "eval_outputs" / "pilot_eval" / "aana-pilot-eval-report.json"


class PilotEvaluationError(RuntimeError):
    pass


def load_kit(path):
    kit = agent_api.load_json_file(path)
    packs = kit.get("packs")
    if not isinstance(packs, list) or not packs:
        raise PilotEvaluationError("Pilot evaluation kit must include a non-empty packs list.")
    for pack in packs:
        if not isinstance(pack, dict) or not pack.get("id"):
            raise PilotEvaluationError("Each pilot evaluation pack must include an id.")
        scenarios = pack.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            raise PilotEvaluationError(f"Pack {pack.get('id')} must include a non-empty scenarios list.")
        for scenario in scenarios:
            if not isinstance(scenario, dict) or not scenario.get("id") or not scenario.get("adapter_id"):
                raise PilotEvaluationError(f"Pack {pack.get('id')} has a scenario missing id or adapter_id.")
    return kit


def selected_packs(kit, selected=None):
    selected = set(selected or [])
    packs = kit["packs"]
    if selected:
        packs = [pack for pack in packs if pack["id"] in selected]
    if not packs:
        raise PilotEvaluationError("No pilot evaluation packs matched the requested selection.")
    return packs


def find_gallery_entry(gallery, adapter_id):
    for entry in gallery.get("adapters", []):
        if entry.get("id") == adapter_id:
            return entry
    raise PilotEvaluationError(f"Unknown adapter id in pilot kit: {adapter_id}")


def expected_for_scenario(kit, scenario, gallery_entry=None, event=None):
    expected = dict(kit.get("default_expected", {}))
    if gallery_entry and isinstance(gallery_entry.get("expected"), dict):
        expected.update(gallery_entry["expected"])
    if event and isinstance(event.get("metadata"), dict):
        metadata = event["metadata"]
        for event_key, expected_key in [
            ("expected_candidate_gate", "candidate_gate"),
            ("expected_gate_decision", "gate_decision"),
            ("expected_recommended_action", "recommended_action"),
            ("expected_aix_decision", "aix_decision"),
            ("expected_candidate_aix_decision", "candidate_aix_decision"),
        ]:
            if metadata.get(event_key) is not None:
                expected[expected_key] = metadata[event_key]
    if isinstance(scenario.get("expected"), dict):
        expected.update(scenario["expected"])
    return expected


def event_from_gallery(kit, scenario, gallery_entry):
    expected = expected_for_scenario(kit, scenario, gallery_entry=gallery_entry)
    return {
        "event_version": agent_api.AGENT_EVENT_VERSION,
        "event_id": scenario["id"],
        "agent": scenario.get("agent", "aana-pilot-eval"),
        "adapter_id": scenario["adapter_id"],
        "user_request": gallery_entry.get("prompt"),
        "candidate_action": gallery_entry.get("bad_candidate"),
        "available_evidence": scenario.get("available_evidence", []),
        "allowed_actions": scenario.get("allowed_actions", ["accept", "revise", "ask", "defer", "refuse"]),
        "metadata": {
            "scenario": scenario["id"],
            "surface": scenario.get("surface"),
            "pack": scenario.get("pack_id"),
            "data_basis": scenario.get("data_basis"),
            "public_data_option": scenario.get("public_data_option"),
            "expected_candidate_gate": expected.get("candidate_gate"),
            "expected_gate_decision": expected.get("gate_decision"),
            "expected_recommended_action": expected.get("recommended_action"),
            "expected_aix_decision": expected.get("aix_decision"),
            "expected_candidate_aix_decision": expected.get("candidate_aix_decision"),
        },
    }


def materialize_event(kit, scenario, gallery):
    source = scenario.get("source", "gallery")
    gallery_entry = find_gallery_entry(gallery, scenario["adapter_id"])
    if source == "agent_event":
        event_path = scenario.get("event_path")
        if not event_path:
            raise PilotEvaluationError(f"Scenario {scenario['id']} uses agent_event but has no event_path.")
        event = agent_api.load_json_file(ROOT / event_path)
        expected = expected_for_scenario(kit, scenario, gallery_entry=gallery_entry, event=event)
        return event, expected
    if source == "gallery":
        event = event_from_gallery(kit, scenario, gallery_entry)
        expected = expected_for_scenario(kit, scenario, gallery_entry=gallery_entry)
        return event, expected
    raise PilotEvaluationError(f"Scenario {scenario['id']} has unsupported source: {source}")


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


def prepare_outputs(audit_log, report_output, json_report_output, metrics_output=None, append=False):
    audit_log = pathlib.Path(audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if append:
        audit_log.touch(exist_ok=True)
    else:
        audit_log.write_text("", encoding="utf-8")

    report_output = pathlib.Path(report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    json_report_output = pathlib.Path(json_report_output)
    json_report_output.parent.mkdir(parents=True, exist_ok=True)

    metrics_output = pathlib.Path(metrics_output) if metrics_output else audit_log.with_name(f"{audit_log.stem}-metrics.json")
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    return audit_log, report_output, json_report_output, metrics_output


def summarize_pack(pack_results):
    passed = sum(1 for item in pack_results if item["passed"])
    return {
        "scenarios": len(pack_results),
        "passed": passed,
        "failed": len(pack_results) - passed,
        "adapters": sorted({item["adapter_id"] for item in pack_results}),
    }


def run_kit(args):
    kit = load_kit(args.kit)
    gallery = agent_api.load_gallery(args.gallery)
    packs = selected_packs(kit, args.pack)
    audit_log, report_output, json_report_output, metrics_output = prepare_outputs(
        args.audit_log,
        args.report_output,
        args.json_report_output,
        metrics_output=args.metrics_output,
        append=args.append,
    )

    pack_reports = []
    flat_results = []
    for pack in packs:
        scenario_reports = []
        for scenario in pack["scenarios"]:
            scenario = dict(scenario)
            scenario["pack_id"] = pack["id"]
            event, expected = materialize_event(kit, scenario, gallery)
            validation = agent_api.validate_event(event)
            if validation["valid"]:
                result = agent_api.check_event(event, gallery_path=args.gallery)
                agent_api.append_audit_record(audit_log, agent_api.audit_event_check(event, result))
                checks, passed = expectation_checks(expected, result)
                scenario_report = {
                    "id": scenario["id"],
                    "pack": pack["id"],
                    "adapter_id": scenario["adapter_id"],
                    "surface": scenario.get("surface", scenario["adapter_id"]),
                    "valid_event": True,
                    "passed": passed,
                    "expected": expected,
                    "expectation_checks": checks,
                    "gate_decision": result.get("gate_decision"),
                    "recommended_action": result.get("recommended_action"),
                    "candidate_gate": result.get("candidate_gate"),
                    "aix_score": result.get("aix", {}).get("score"),
                    "aix_decision": result.get("aix", {}).get("decision"),
                    "candidate_aix_score": result.get("candidate_aix", {}).get("score"),
                    "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
                    "violations": [violation.get("code") for violation in result.get("violations", [])],
                    "data_basis": scenario.get("data_basis"),
                    "public_data_option": scenario.get("public_data_option"),
                    "operator_workflow": scenario.get("operator_workflow"),
                }
            else:
                scenario_report = {
                    "id": scenario["id"],
                    "pack": pack["id"],
                    "adapter_id": scenario["adapter_id"],
                    "surface": scenario.get("surface", scenario["adapter_id"]),
                    "valid_event": False,
                    "passed": False,
                    "validation": validation,
                    "expected": expected,
                    "data_basis": scenario.get("data_basis"),
                    "public_data_option": scenario.get("public_data_option"),
                    "operator_workflow": scenario.get("operator_workflow"),
                }
            scenario_reports.append(scenario_report)
            flat_results.append(scenario_report)
        pack_reports.append(
            {
                "id": pack["id"],
                "title": pack.get("title"),
                "goal": pack.get("goal"),
                "pilot_surface": pack.get("pilot_surface", {}),
                "summary": summarize_pack(scenario_reports),
                "scenarios": scenario_reports,
            }
        )

    metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_output)
    failed = [item for item in flat_results if not item["passed"]]
    report = {
        "pilot_evaluation_kit_version": kit.get("kit_version"),
        "valid": not failed,
        "summary": {
            "packs": len(pack_reports),
            "scenarios": len(flat_results),
            "passed": len(flat_results) - len(failed),
            "failed": len(failed),
            "audit_records": metrics["record_count"],
            "metrics_output": str(metrics_output),
            "audit_log": str(audit_log),
            "markdown_report": str(report_output),
        },
        "public_data_options": kit.get("public_data_options", []),
        "packs": pack_reports,
        "metrics": metrics,
    }

    json_report_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_output.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def render_markdown_report(report):
    summary = report["summary"]
    metrics = report["metrics"].get("metrics", {})
    lines = [
        "# AANA Pilot Evaluation Report",
        "",
        f"Status: {'PASS' if report['valid'] else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Packs: {summary['packs']}",
        f"- Scenarios: {summary['scenarios']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Audit records: {summary['audit_records']}",
        f"- Audit log: `{summary['audit_log']}`",
        f"- Metrics JSON: `{summary['metrics_output']}`",
        "",
        "## Core Metrics",
        "",
    ]
    for key in [
        "gate_decision_count",
        "recommended_action_count",
        "violation_code_count",
        "adapter_check_count",
        "aix_score_average",
        "aix_score_min",
        "aix_score_max",
        "aix_decision_count",
        "aix_hard_blocker_count",
    ]:
        if key in metrics:
            lines.append(f"- `{key}`: {metrics[key]}")
    lines.extend(["", "## Packs", ""])
    for pack in report["packs"]:
        pack_summary = pack["summary"]
        lines.extend(
            [
                f"### {pack['title'] or pack['id']}",
                "",
                pack.get("goal") or "",
                "",
                f"- Scenarios: {pack_summary['scenarios']}",
                f"- Passed: {pack_summary['passed']}",
                f"- Failed: {pack_summary['failed']}",
                f"- Adapters: {', '.join(pack_summary['adapters'])}",
                "",
                "Pilot surface:",
                "",
            ]
        )
        surface = pack.get("pilot_surface", {})
        if surface:
            lines.extend(
                [
                    f"- Entry point: {surface.get('entrypoint', '')}",
                    f"- Operating mode: {surface.get('operating_mode', '')}",
                    f"- Primary users: {', '.join(surface.get('primary_users', []))}",
                    f"- Evidence systems: {', '.join(surface.get('evidence_systems', []))}",
                    "",
                ]
            )
        lines.extend(
            [
                "| Scenario | Surface | Adapter | Status | Gate | Action | AIx | Data Basis | Operator Workflow |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for scenario in pack["scenarios"]:
            status = "PASS" if scenario["passed"] else "FAIL"
            lines.append(
                "| {id} | {surface} | {adapter} | {status} | {gate} | {action} | {aix} | {basis} | {workflow} |".format(
                    id=scenario["id"],
                    surface=scenario.get("surface", scenario["adapter_id"]),
                    adapter=scenario["adapter_id"],
                    status=status,
                    gate=scenario.get("gate_decision", ""),
                    action=scenario.get("recommended_action", ""),
                    aix=scenario.get("aix_decision", ""),
                    basis=scenario.get("data_basis", ""),
                    workflow=(scenario.get("operator_workflow") or "").replace("|", "/"),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Public Data Rehearsal Options",
            "",
            "These are source families for creating richer non-private fixtures. They are not fetched by this script.",
            "",
        ]
    )
    for option in report.get("public_data_options", []):
        lines.append(f"- `{option.get('id')}`: {option.get('name')} - {option.get('use')}")
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the AANA Pilot Evaluation Kit.")
    parser.add_argument("--kit", default=DEFAULT_KIT, help="Pilot evaluation kit JSON manifest.")
    parser.add_argument("--pack", action="append", default=[], help="Run only this pack id. Repeat as needed.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted audit JSONL output path.")
    parser.add_argument("--metrics-output", default=None, help="Audit metrics JSON output path.")
    parser.add_argument("--report-output", default=DEFAULT_REPORT, help="Markdown report output path.")
    parser.add_argument("--json-report-output", default=DEFAULT_JSON_REPORT, help="JSON report output path.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        report = run_kit(args)
    except (PilotEvaluationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA pilot evaluation kit: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["valid"] else "FAIL"
        summary = report["summary"]
        print(f"AANA pilot evaluation kit: {status}")
        print(f"- Packs: {summary['packs']}")
        print(f"- Scenarios: {summary['scenarios']}")
        print(f"- Passed: {summary['passed']}")
        print(f"- Failed: {summary['failed']}")
        print(f"- Audit log: {summary['audit_log']}")
        print(f"- Metrics JSON: {summary['metrics_output']}")
        print(f"- Markdown report: {summary['markdown_report']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
