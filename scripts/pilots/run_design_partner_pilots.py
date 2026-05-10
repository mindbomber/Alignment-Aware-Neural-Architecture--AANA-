#!/usr/bin/env python
"""Run controlled AANA design-partner pilot bundles."""

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_INDEX = ROOT / "examples" / "design_partner_pilots" / "index.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_OUTPUT_ROOT = ROOT / "eval_outputs" / "design_partner_pilots"
DEFAULT_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]


class DesignPartnerPilotError(RuntimeError):
    pass


def load_json(path):
    path = pathlib.Path(path)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise DesignPartnerPilotError(f"{path} must contain a JSON object.")
    return data


def write_json(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_index(path=DEFAULT_INDEX):
    index = load_json(path)
    pilots = index.get("pilots")
    if not isinstance(pilots, list) or not pilots:
        raise DesignPartnerPilotError("Design-partner index must include a non-empty pilots list.")
    for pilot in pilots:
        if not isinstance(pilot, dict):
            raise DesignPartnerPilotError("Each design-partner pilot must be an object.")
        for field in ("id", "category", "title", "partner_profile", "workflows", "collection_plan"):
            if field not in pilot:
                raise DesignPartnerPilotError(f"Design-partner pilot is missing required field: {field}")
        if not isinstance(pilot["workflows"], list) or not pilot["workflows"]:
            raise DesignPartnerPilotError(f"Pilot {pilot['id']} must include a non-empty workflows list.")
    return index


def selected_pilots(index, selections):
    requested = set(selections or ["all"])
    pilots = index["pilots"]
    if "all" not in requested:
        pilots = [pilot for pilot in pilots if pilot["id"] in requested]
    missing = requested - {"all"} - {pilot["id"] for pilot in index["pilots"]}
    if missing:
        raise DesignPartnerPilotError("Unknown design-partner pilot id(s): " + ", ".join(sorted(missing)))
    if not pilots:
        raise DesignPartnerPilotError("No design-partner pilots matched the requested selection.")
    return pilots


def find_gallery_entry(gallery, adapter_id):
    for entry in gallery.get("adapters", []):
        if entry.get("id") == adapter_id:
            return entry
    raise DesignPartnerPilotError(f"Unknown adapter id in design-partner pilot: {adapter_id}")


def prepare_output_dir(output_root, pilot_id, append=False):
    output_dir = pathlib.Path(output_root) / pilot_id
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
        "dashboard": output_dir / "dashboard.json",
        "drift": output_dir / "aix_drift.json",
        "manifest": output_dir / "audit_integrity_manifest.json",
        "reviewer_report": output_dir / "reviewer_report.md",
        "report_json": output_dir / "report.json",
        "report_md": output_dir / "report.md",
        "batch": output_dir / "workflow_batch.json",
        "feedback_template": output_dir / "feedback_template.json",
        "field_notes": output_dir / "field_notes_template.md",
    }


def evidence_object(pilot, workflow):
    return {
        "source_id": workflow.get("source_id") or f"synthetic-{workflow['adapter_id']}",
        "retrieved_at": "2026-05-05T00:00:00Z",
        "trust_tier": "synthetic",
        "redaction_status": "synthetic",
        "text": workflow.get("evidence_summary")
        or f"Synthetic design-partner evidence for {pilot['category']} workflow {workflow['workflow_id']}.",
    }


def materialize_workflow(pilot, workflow, gallery_entry):
    expected = gallery_entry.get("expected", {}) if isinstance(gallery_entry.get("expected"), dict) else {}
    return {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow["workflow_id"],
        "adapter": workflow["adapter_id"],
        "request": workflow.get("request") or gallery_entry.get("prompt", ""),
        "candidate": workflow.get("candidate") or gallery_entry.get("bad_candidate", ""),
        "evidence": [evidence_object(pilot, workflow)],
        "constraints": workflow.get("constraints") or [gallery_entry.get("workflow", "")],
        "allowed_actions": workflow.get("allowed_actions", DEFAULT_ALLOWED_ACTIONS),
        "metadata": {
            "design_partner_pilot": pilot["id"],
            "category": pilot["category"],
            "workflow_label": workflow.get("label"),
            "data_basis": "synthetic_or_redacted_partner_input",
            "partner_profile": pilot.get("partner_profile", {}),
            "expected_candidate_gate": expected.get("candidate_gate"),
            "expected_gate_decision": expected.get("gate_decision"),
            "expected_recommended_action": expected.get("recommended_action"),
            "expected_aix_decision": expected.get("aix_decision"),
            "expected_candidate_aix_decision": expected.get("candidate_aix_decision"),
        },
    }


def expectation_checks(workflow, result):
    expected = workflow.get("metadata", {})
    checks = {
        "candidate_gate": result.get("candidate_gate") == expected.get("expected_candidate_gate"),
        "gate_decision": result.get("gate_decision") == expected.get("expected_gate_decision"),
        "recommended_action": result.get("recommended_action") == expected.get("expected_recommended_action"),
        "aix_decision": result.get("aix", {}).get("decision") == expected.get("expected_aix_decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision")
        == expected.get("expected_candidate_aix_decision"),
    }
    return checks, all(checks.values())


def scenario_report(workflow, result, passed, checks):
    aix = result.get("aix", {}) if isinstance(result.get("aix"), dict) else {}
    candidate_aix = result.get("candidate_aix", {}) if isinstance(result.get("candidate_aix"), dict) else {}
    violations = [violation.get("code") for violation in result.get("violations", []) if isinstance(violation, dict)]
    return {
        "workflow_id": workflow["workflow_id"],
        "adapter_id": workflow["adapter"],
        "label": workflow.get("metadata", {}).get("workflow_label"),
        "passed_expected_outcome": passed,
        "expectation_checks": checks,
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "candidate_aix_score": candidate_aix.get("score"),
        "candidate_aix_decision": candidate_aix.get("decision"),
        "violation_codes": violations,
    }


def feedback_template(pilot):
    return {
        "design_partner_feedback_version": "0.1",
        "pilot_id": pilot["id"],
        "partner": {
            "organization_alias": "",
            "reviewer_role": "",
            "review_date": "",
            "data_classification_used": "synthetic_or_redacted",
        },
        "pilot_decision": "unknown",
        "failure_modes": [
            {
                "workflow_id": "",
                "description": "",
                "severity": "low|medium|high",
                "aana_missed_risk": False,
                "aana_overblocked": False,
                "evidence_gap": False,
                "notes": "",
            }
        ],
        "friction_points": [
            {
                "surface": "cli|python_api|http_bridge|adapter|evidence|audit|metrics|docs|workflow_fit",
                "description": "",
                "impact": "low|medium|high",
                "suggested_change": "",
            }
        ],
        "adoption_blockers": [
            {
                "blocker_type": "security_review|data_access|workflow_fit|latency|false_positive|false_negative|human_review|procurement|trust|other",
                "description": "",
                "owner": "",
                "next_step": "",
            }
        ],
    }


def render_field_notes_template(pilot):
    prompts = pilot.get("collection_plan", {})
    lines = [
        f"# Design Partner Field Notes: {pilot['title']}",
        "",
        f"- Pilot id: `{pilot['id']}`",
        f"- Category: `{pilot['category']}`",
        "- Data rule: use synthetic or redacted partner data only.",
        "",
        "## Session Summary",
        "",
        "- Organization alias:",
        "- Reviewer role:",
        "- Date:",
        "- Surface used: CLI / Python API / HTTP bridge / playground / workflow batch",
        "- Continue, pause, or stop:",
        "",
        "## Failure Modes",
        "",
    ]
    for item in prompts.get("failure_mode_prompts", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Friction Points", ""])
    for item in prompts.get("friction_prompts", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Adoption Blockers", ""])
    for item in prompts.get("adoption_blocker_prompts", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Open Follow-ups", "", "- "])
    return "\n".join(lines) + "\n"


def load_partner_feedback(feedback_dir, pilot_id):
    if not feedback_dir:
        return None
    path = pathlib.Path(feedback_dir) / f"{pilot_id}.json"
    if not path.exists():
        return None
    return load_json(path)


def feedback_summary(feedback):
    if not feedback:
        return {
            "status": "pending_partner_feedback",
            "failure_modes": 0,
            "friction_points": 0,
            "adoption_blockers": 0,
            "pilot_decision": "unknown",
        }
    return {
        "status": "feedback_attached",
        "failure_modes": len(feedback.get("failure_modes", [])) if isinstance(feedback.get("failure_modes"), list) else 0,
        "friction_points": len(feedback.get("friction_points", [])) if isinstance(feedback.get("friction_points"), list) else 0,
        "adoption_blockers": len(feedback.get("adoption_blockers", [])) if isinstance(feedback.get("adoption_blockers"), list) else 0,
        "pilot_decision": feedback.get("pilot_decision", "unknown"),
    }


def render_markdown_report(report):
    summary = report["summary"]
    lines = [
        f"# AANA Design Partner Pilot: {report['title']}",
        "",
        f"Status: {'PASS' if report['valid'] else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Pilot id: `{report['pilot_id']}`",
        f"- Category: `{report['category']}`",
        f"- Workflows: {summary['workflows']}",
        f"- Expected outcomes passed: {summary['expected_outcomes_passed']}",
        f"- Audit records: {summary['audit_records']}",
        f"- Feedback status: {report['feedback_summary']['status']}",
        f"- Failure modes captured: {report['feedback_summary']['failure_modes']}",
        f"- Friction points captured: {report['feedback_summary']['friction_points']}",
        f"- Adoption blockers captured: {report['feedback_summary']['adoption_blockers']}",
        "",
        "## Artifacts",
        "",
        f"- Audit log: `{summary['audit_log']}`",
        f"- Metrics: `{summary['metrics']}`",
        f"- Dashboard payload: `{summary['dashboard']}`",
        f"- AIx drift: `{summary['drift']}`",
        f"- Audit manifest: `{summary['manifest']}`",
        f"- Reviewer report: `{summary['reviewer_report']}`",
        f"- Feedback template: `{summary['feedback_template']}`",
        f"- Field notes template: `{summary['field_notes']}`",
        "",
        "## Workflows",
        "",
        "| Workflow | Adapter | Expected | Gate | Action | Candidate Gate | AIx | Candidate AIx | Violations |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scenario in report["scenarios"]:
        lines.append(
            "| {workflow} | {adapter} | {expected} | {gate} | {action} | {candidate_gate} | {aix} | {candidate_aix} | {violations} |".format(
                workflow=scenario["workflow_id"],
                adapter=scenario["adapter_id"],
                expected="PASS" if scenario["passed_expected_outcome"] else "FAIL",
                gate=scenario.get("gate_decision", ""),
                action=scenario.get("recommended_action", ""),
                candidate_gate=scenario.get("candidate_gate", ""),
                aix=scenario.get("aix_decision", ""),
                candidate_aix=scenario.get("candidate_aix_decision", ""),
                violations=", ".join(scenario.get("violation_codes", [])),
            )
        )
    return "\n".join(lines) + "\n"


def run_pilot(pilot, args):
    gallery = agent_api.load_gallery(args.gallery)
    outputs = prepare_output_dir(args.output_root, pilot["id"], append=args.append)
    workflows = []
    scenarios = []
    for workflow_spec in pilot["workflows"]:
        for field in ("workflow_id", "adapter_id"):
            if field not in workflow_spec:
                raise DesignPartnerPilotError(f"Pilot {pilot['id']} workflow is missing {field}.")
        gallery_entry = find_gallery_entry(gallery, workflow_spec["adapter_id"])
        workflow = materialize_workflow(pilot, workflow_spec, gallery_entry)
        validation = agent_api.validate_workflow_request(workflow)
        if not validation["valid"]:
            messages = "; ".join(issue["message"] for issue in validation["issues"] if issue["level"] == "error")
            raise DesignPartnerPilotError(f"Workflow {workflow['workflow_id']} is invalid: {messages}")
        result = agent_api.check_workflow_request(workflow, gallery_path=args.gallery)
        if args.shadow_mode:
            result = agent_api.apply_shadow_mode(result)
        agent_api.append_audit_record(outputs["audit_log"], agent_api.audit_workflow_check(workflow, result))
        checks, passed = expectation_checks(workflow, result)
        workflows.append(workflow)
        scenarios.append(scenario_report(workflow, result, passed, checks))

    batch = {
        "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
        "batch_id": f"{pilot['id']}-design-partner-pilot",
        "requests": workflows,
    }
    write_json(outputs["batch"], batch)
    metrics = agent_api.export_audit_metrics_file(outputs["audit_log"], output_path=outputs["metrics"])
    dashboard = agent_api.audit_dashboard_file(outputs["audit_log"])
    write_json(outputs["dashboard"], dashboard)
    drift = agent_api.audit_aix_drift_report_file(outputs["audit_log"], output_path=outputs["drift"])
    manifest = agent_api.create_audit_integrity_manifest(outputs["audit_log"], manifest_path=outputs["manifest"])
    reviewer = agent_api.write_audit_reviewer_report(
        outputs["audit_log"],
        outputs["reviewer_report"],
        metrics_path=outputs["metrics"],
        drift_report_path=outputs["drift"],
        manifest_path=outputs["manifest"],
    )
    template = feedback_template(pilot)
    write_json(outputs["feedback_template"], template)
    outputs["field_notes"].write_text(render_field_notes_template(pilot), encoding="utf-8")

    feedback = load_partner_feedback(args.feedback_dir, pilot["id"])
    failed_expectations = [scenario for scenario in scenarios if not scenario["passed_expected_outcome"]]
    report = {
        "design_partner_pilot_report_version": "0.1",
        "valid": not failed_expectations and metrics.get("record_count") == len(scenarios),
        "pilot_id": pilot["id"],
        "category": pilot["category"],
        "title": pilot["title"],
        "partner_profile": pilot["partner_profile"],
        "feedback_summary": feedback_summary(feedback),
        "feedback": feedback,
        "summary": {
            "workflows": len(scenarios),
            "expected_outcomes_passed": len(scenarios) - len(failed_expectations),
            "expected_outcomes_failed": len(failed_expectations),
            "audit_records": metrics.get("record_count"),
            "audit_log": str(outputs["audit_log"]),
            "metrics": str(outputs["metrics"]),
            "dashboard": str(outputs["dashboard"]),
            "drift": str(outputs["drift"]),
            "manifest": str(outputs["manifest"]),
            "reviewer_report": str(reviewer["output_path"]),
            "workflow_batch": str(outputs["batch"]),
            "feedback_template": str(outputs["feedback_template"]),
            "field_notes": str(outputs["field_notes"]),
        },
        "collection_plan": pilot["collection_plan"],
        "scenarios": scenarios,
        "metrics": metrics,
        "drift": drift,
        "manifest": manifest,
    }
    write_json(outputs["report_json"], report)
    outputs["report_md"].write_text(render_markdown_report(report), encoding="utf-8")
    return report


def run_selected(args):
    index = load_index(args.index)
    pilots = selected_pilots(index, args.pilot)
    reports = [run_pilot(pilot, args) for pilot in pilots]
    failed = [report for report in reports if not report["valid"]]
    return {
        "design_partner_pilots_report_version": "0.1",
        "valid": not failed,
        "summary": {
            "pilots": len(reports),
            "passed": len(reports) - len(failed),
            "failed": len(failed),
            "workflows": sum(report["summary"]["workflows"] for report in reports),
            "audit_records": sum(report["summary"]["audit_records"] for report in reports),
            "feedback_attached": sum(1 for report in reports if report["feedback_summary"]["status"] == "feedback_attached"),
            "failure_modes": sum(report["feedback_summary"]["failure_modes"] for report in reports),
            "friction_points": sum(report["feedback_summary"]["friction_points"] for report in reports),
            "adoption_blockers": sum(report["feedback_summary"]["adoption_blockers"] for report in reports),
            "output_root": str(pathlib.Path(args.output_root)),
        },
        "pilots": reports,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run controlled AANA design-partner pilots.")
    parser.add_argument("--pilot", action="append", default=None, help="Pilot id to run. Repeat as needed, or use all.")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Design-partner pilot index JSON.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory for generated pilot artifacts.")
    parser.add_argument("--feedback-dir", default=None, help="Optional directory with <pilot_id>.json partner feedback files.")
    parser.add_argument("--append", action="store_true", help="Append to existing audit logs instead of starting fresh.")
    parser.add_argument("--shadow-mode", action="store_true", help="Record observe-only audit semantics.")
    parser.add_argument("--json", action="store_true", help="Print the combined JSON report.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        report = run_selected(args)
    except (DesignPartnerPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA design-partner pilots: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["valid"] else "FAIL"
        summary = report["summary"]
        print(f"AANA design-partner pilots: {status}")
        print(f"- Pilots: {summary['pilots']}")
        print(f"- Workflows: {summary['workflows']}")
        print(f"- Audit records: {summary['audit_records']}")
        print(f"- Feedback attached: {summary['feedback_attached']}")
        print(f"- Failure modes: {summary['failure_modes']}")
        print(f"- Friction points: {summary['friction_points']}")
        print(f"- Adoption blockers: {summary['adoption_blockers']}")
        print(f"- Output root: {summary['output_root']}")
        for pilot in report["pilots"]:
            print(
                f"- {pilot['pilot_id']}: {pilot['summary']['expected_outcomes_passed']}/"
                f"{pilot['summary']['workflows']} expected outcomes passed"
            )
            print(f"  report: {pathlib.Path(pilot['summary']['workflow_batch']).parent / 'report.md'}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
