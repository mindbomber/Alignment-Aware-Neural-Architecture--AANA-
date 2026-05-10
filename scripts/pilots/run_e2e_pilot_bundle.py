#!/usr/bin/env python
"""Run an end-to-end AANA pilot bundle across multiple adapters."""

import argparse
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api
from scripts import aana_cli


DEFAULT_EVENTS_DIR = ROOT / "examples" / "agent_events"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "aana-e2e-pilot.jsonl"
DEFAULT_DEPLOYMENT = ROOT / "examples" / "production_deployment_internal_pilot.json"
DEFAULT_GOVERNANCE = ROOT / "examples" / "human_governance_policy_internal_pilot.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "examples" / "evidence_registry.json"
DEFAULT_OBSERVABILITY = ROOT / "examples" / "observability_policy_internal_pilot.json"


class PilotBundleError(RuntimeError):
    pass


def discover_events(events_dir, selected=None):
    selected = set(selected or [])
    paths = list(agent_api.discover_agent_events(events_dir))
    if selected:
        paths = [
            path
            for path in paths
            if path.stem in selected or agent_api.load_json_file(path).get("adapter_id") in selected
        ]
    if not paths:
        raise PilotBundleError("No pilot event files matched the requested selection.")
    return paths


def prepare_output_paths(audit_log, metrics_output=None, manifest_output=None, append=False):
    audit_log = pathlib.Path(audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        audit_log.write_text("", encoding="utf-8")
    elif not audit_log.exists():
        audit_log.touch()

    if metrics_output:
        metrics_path = pathlib.Path(metrics_output)
    else:
        metrics_path = audit_log.with_name(f"{audit_log.stem}-metrics.json")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_output:
        manifest_path = pathlib.Path(manifest_output)
    else:
        manifest_path = audit_log.parent / "manifests" / f"{audit_log.stem}-integrity.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return audit_log, metrics_path, manifest_path


def event_expectations_pass(event, result):
    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    checks = {
        "candidate_gate": metadata.get("expected_candidate_gate") is None
        or result.get("candidate_gate") == metadata.get("expected_candidate_gate"),
        "gate_decision": metadata.get("expected_gate_decision") is None
        or result.get("gate_decision") == metadata.get("expected_gate_decision"),
        "recommended_action": metadata.get("expected_recommended_action") is None
        or result.get("recommended_action") == metadata.get("expected_recommended_action"),
        "aix_decision": metadata.get("expected_aix_decision") is None
        or result.get("aix", {}).get("decision") == metadata.get("expected_aix_decision"),
        "candidate_aix_decision": metadata.get("expected_candidate_aix_decision") is None
        or result.get("candidate_aix", {}).get("decision") == metadata.get("expected_candidate_aix_decision"),
    }
    return all(checks.values()), checks


def run_event_checks(event_paths, gallery, audit_log):
    checked = []
    for path in event_paths:
        event = agent_api.load_json_file(path)
        validation = agent_api.validate_event(event)
        if not validation["valid"]:
            checked.append(
                {
                    "event_file": str(path),
                    "event_id": event.get("event_id"),
                    "adapter_id": event.get("adapter_id"),
                    "valid": False,
                    "passed_expectations": False,
                    "validation": validation,
                }
            )
            continue

        result = agent_api.check_event(event, gallery_path=gallery)
        record = agent_api.audit_event_check(event, result)
        agent_api.append_audit_record(audit_log, record)
        passed, expectation_checks = event_expectations_pass(event, result)
        checked.append(
            {
                "event_file": str(path),
                "event_id": event.get("event_id"),
                "adapter_id": result.get("adapter_id"),
                "valid": True,
                "gate_decision": result.get("gate_decision"),
                "recommended_action": result.get("recommended_action"),
                "candidate_gate": result.get("candidate_gate"),
                "aix_decision": result.get("aix", {}).get("decision"),
                "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
                "passed_expectations": passed,
                "expectation_checks": expectation_checks,
                "validation": validation,
            }
        )
    return checked


def run_production_profiles():
    completed = subprocess.run(
        [sys.executable, "scripts/dev.py", "production-profiles"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": "python scripts/dev.py production-profiles",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_bundle(args):
    audit_log, metrics_path, manifest_path = prepare_output_paths(
        args.audit_log,
        metrics_output=args.metrics_output,
        manifest_output=args.manifest_output,
        append=args.append,
    )
    event_paths = discover_events(args.events_dir, selected=args.event)
    checked = run_event_checks(event_paths, args.gallery, audit_log)
    event_failures = [item for item in checked if not item.get("valid") or not item.get("passed_expectations")]

    metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_path)
    integrity = agent_api.create_audit_integrity_manifest(audit_log, manifest_path=manifest_path)
    release = aana_cli.release_check_report(
        gallery_path=args.gallery,
        deployment_manifest=args.deployment_manifest,
        governance_policy=args.governance_policy,
        evidence_registry=args.evidence_registry,
        observability_policy=args.observability_policy,
        audit_log=audit_log,
        run_local_check=False,
    )
    production_profiles = (
        {"command": "python scripts/dev.py production-profiles", "skipped": True, "passed": True}
        if args.skip_production_profiles
        else run_production_profiles()
    )

    valid = not event_failures and release["valid"] and production_profiles["passed"]
    return {
        "pilot_bundle_version": "0.1",
        "valid": valid,
        "summary": {
            "events_checked": len(checked),
            "event_failures": len(event_failures),
            "audit_records": metrics["record_count"],
            "release_check_status": release["summary"]["status"],
            "production_profiles": "skipped" if production_profiles.get("skipped") else "pass" if production_profiles["passed"] else "fail",
        },
        "events": checked,
        "audit": {
            "audit_log": str(audit_log),
            "metrics": str(metrics_path),
            "integrity_manifest": str(manifest_path),
            "integrity_manifest_sha256": integrity["manifest_sha256"],
            "metrics_summary": {
                "record_count": metrics["record_count"],
                "aix_score_average": metrics["metrics"].get("aix_score_average"),
                "aix_hard_blocker_count": metrics["metrics"].get("aix_hard_blocker_count"),
                "aix_decision_count": metrics["metrics"].get("aix_decision_count"),
                "gate_decision_count": metrics["metrics"].get("gate_decision_count"),
                "recommended_action_count": metrics["metrics"].get("recommended_action_count"),
            },
        },
        "release_check": release,
        "production_profiles": production_profiles,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run an end-to-end AANA pilot scenario bundle.")
    parser.add_argument("--events-dir", default=DEFAULT_EVENTS_DIR, help="Directory containing agent event JSON files.")
    parser.add_argument("--event", action="append", default=[], help="Run only this event stem or adapter id. Repeat as needed.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted audit JSONL output path.")
    parser.add_argument("--metrics-output", default=None, help="Audit metrics JSON output path.")
    parser.add_argument("--manifest-output", default=None, help="Audit integrity manifest output path.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting a fresh pilot log.")
    parser.add_argument("--deployment-manifest", default=DEFAULT_DEPLOYMENT, help="Deployment manifest for release-check.")
    parser.add_argument("--governance-policy", default=DEFAULT_GOVERNANCE, help="Governance policy for release-check.")
    parser.add_argument("--evidence-registry", default=DEFAULT_EVIDENCE_REGISTRY, help="Evidence registry for release-check.")
    parser.add_argument("--observability-policy", default=DEFAULT_OBSERVABILITY, help="Observability policy for release-check.")
    parser.add_argument("--skip-production-profiles", action="store_true", help="Skip python scripts/dev.py production-profiles.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_bundle(args)
    except (PilotBundleError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA e2e pilot bundle: FAIL - {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"AANA e2e pilot bundle: {status}")
        print(f"- Events checked: {result['summary']['events_checked']}")
        print(f"- Event failures: {result['summary']['event_failures']}")
        print(f"- Audit log: {result['audit']['audit_log']}")
        print(f"- Audit metrics: {result['audit']['metrics']}")
        print(f"- Audit integrity manifest: {result['audit']['integrity_manifest']}")
        print(f"- Audit records: {result['summary']['audit_records']}")
        print(f"- Release check: {result['summary']['release_check_status']}")
        print(f"- Production profiles: {result['summary']['production_profiles']}")
        for item in result["events"]:
            expectation = "ok" if item.get("passed_expectations") else "unexpected"
            print(
                f"  - {item.get('adapter_id')}: gate={item.get('gate_decision')} "
                f"action={item.get('recommended_action')} aix={item.get('aix_decision')} "
                f"expectations={expectation}"
            )
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
