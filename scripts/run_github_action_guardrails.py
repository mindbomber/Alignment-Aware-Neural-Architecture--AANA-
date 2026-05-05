#!/usr/bin/env python
"""Run AANA guardrail adapters from GitHub Actions evidence."""

import argparse
import json
import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_OUTPUT_DIR = pathlib.Path("eval_outputs") / "github_action" / "aana-guardrails"
DEFAULT_ADAPTERS = [
    "code_change_review",
    "deployment_readiness",
    "api_contract_change",
    "infrastructure_change_guardrail",
    "database_migration_guardrail",
]
DEFAULT_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]
SNIPPET_LIMIT = 12000


class GitHubGuardrailError(RuntimeError):
    pass


def run_git(args, repo_root):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def git_ref_exists(repo_root, ref):
    if not ref:
        return False
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo_root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return completed.returncode == 0


def normalize_base_ref(repo_root, base_ref):
    if not base_ref:
        return ""
    if git_ref_exists(repo_root, base_ref):
        return base_ref
    origin_ref = f"origin/{base_ref}"
    if "/" not in base_ref and git_ref_exists(repo_root, origin_ref):
        return origin_ref
    return base_ref


def split_values(value):
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = []
        for chunk in str(value).replace("\n", ",").split(","):
            raw.append(chunk)
    return [item.strip() for item in raw if item and item.strip()]


def read_text(path, repo_root=None, limit=SNIPPET_LIMIT):
    if not path:
        return ""
    candidate = pathlib.Path(path)
    if repo_root and not candidate.is_absolute():
        candidate = pathlib.Path(repo_root) / candidate
    if not candidate.is_file():
        return ""
    text = candidate.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + f"\n...[truncated at {limit} characters]"
    return text


def compact_text(text, limit=SNIPPET_LIMIT):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated at {limit} characters]"


def current_ref_range(base_ref=None, head_ref=None):
    if base_ref and head_ref:
        return f"{base_ref}...{head_ref}"
    if base_ref:
        return f"{base_ref}...HEAD"
    return ""


def changed_files(repo_root, base_ref=None, head_ref=None, explicit=None):
    explicit_files = split_values(explicit)
    if explicit_files:
        return explicit_files
    base_ref = normalize_base_ref(repo_root, base_ref)
    ref_range = current_ref_range(base_ref, head_ref)
    if ref_range:
        output = run_git(["diff", "--name-only", ref_range], repo_root)
        files = split_values(output)
        if files:
            return files
    output = run_git(["diff", "--name-only", "HEAD"], repo_root)
    files = split_values(output)
    if files:
        return files
    output = run_git(["status", "--short"], repo_root)
    return [line[3:].strip() for line in output.splitlines() if len(line) > 3]


def diff_text(repo_root, base_ref=None, head_ref=None, diff_file=None):
    explicit = read_text(diff_file, repo_root=repo_root)
    if explicit:
        return compact_text(explicit)
    base_ref = normalize_base_ref(repo_root, base_ref)
    ref_range = current_ref_range(base_ref, head_ref)
    if ref_range:
        output = run_git(["diff", "--no-ext-diff", "--unified=2", ref_range], repo_root)
        if output:
            return compact_text(output)
    output = run_git(["diff", "--no-ext-diff", "--unified=2", "HEAD"], repo_root)
    return compact_text(output)


def file_matches(files, terms):
    lowered = [item.lower().replace("\\", "/") for item in files]
    return any(any(term in item for term in terms) for item in lowered)


def evidence_object(source_id, text, trust_tier="verified", redaction_status="redacted"):
    return {
        "source_id": source_id,
        "trust_tier": trust_tier,
        "redaction_status": redaction_status,
        "text": text or "No evidence supplied.",
    }


def adapter_relevant(adapter_id, files, args):
    if args.force:
        return True
    if adapter_id == "code_change_review":
        return bool(files) or bool(args.diff_file)
    if adapter_id == "deployment_readiness":
        return bool(args.deployment_manifest or args.release_notes) or file_matches(
            files,
            ["deploy", "deployment", "release", "helm", "k8s", "kubernetes", ".github/workflows"],
        )
    if adapter_id == "api_contract_change":
        return bool(args.openapi_diff or args.consumer_list) or file_matches(
            files,
            ["openapi", "swagger", "api/", "apis/", "schema", "contract"],
        )
    if adapter_id == "infrastructure_change_guardrail":
        return bool(args.iac_plan) or file_matches(
            files,
            [".tf", ".tfvars", "terraform", "tofu", "infra/", "infrastructure/", "cloudformation", "pulumi"],
        )
    if adapter_id == "database_migration_guardrail":
        return bool(args.migration_diff or args.schema_state or args.backup_status or args.rollout_plan) or file_matches(
            files,
            ["migration", "migrations/", "alembic", "db/", "database/", ".sql", "schema.prisma"],
        )
    return True


def build_check(adapter_id, files, diff, args):
    ci_status = args.ci_status or os.getenv("AANA_CI_STATUS") or os.getenv("GITHUB_JOB") or "unknown"
    test_output = read_text(args.test_output, repo_root=args.repo_root) or "No test output artifact supplied."
    files_text = ", ".join(files[:80]) if files else "No changed files detected."
    common = [
        evidence_object("github-changed-files", f"Changed files: {files_text}"),
        evidence_object("github-diff", f"Git diff excerpt:\n{diff or 'No diff excerpt available.'}"),
        evidence_object("github-ci-status", f"CI status: {ci_status}"),
    ]

    if adapter_id == "code_change_review":
        evidence = common + [evidence_object("github-test-output", f"Test output excerpt:\n{test_output}")]
        candidate = (
            "Review this pull request before merge. "
            f"CI status: {ci_status}. Test output: {test_output}. "
            f"Changed files: {files_text}. Diff excerpt: {diff}."
        )
        return {
            "adapter": adapter_id,
            "request": "Check this GitHub pull request before merge using diff, test output, CI status, and changed-file scope evidence.",
            "candidate": candidate,
            "evidence": evidence,
            "constraints": [
                "Verify tests and CI before accepting.",
                "Keep diff scope aligned with the requested change.",
                "Block secrets and destructive commands.",
                "Escalate migration risk.",
            ],
        }

    if adapter_id == "deployment_readiness":
        manifest = read_text(args.deployment_manifest, repo_root=args.repo_root) or "No deployment manifest artifact supplied."
        release_notes = read_text(args.release_notes, repo_root=args.repo_root) or "No release notes artifact supplied."
        evidence = common + [
            evidence_object("deployment-manifest", f"Deployment manifest excerpt:\n{manifest}"),
            evidence_object("release-notes", f"Release notes excerpt:\n{release_notes}"),
        ]
        candidate = (
            "Review this deployment before release. "
            f"CI status: {ci_status}. Deployment manifest: {manifest}. Release notes: {release_notes}. Diff excerpt: {diff}."
        )
        return {
            "adapter": adapter_id,
            "request": "Check deployment readiness before production release.",
            "candidate": candidate,
            "evidence": evidence,
            "constraints": [
                "Verify config, secrets, rollback, health checks, migrations, and observability.",
            ],
        }

    if adapter_id == "api_contract_change":
        openapi_diff = read_text(args.openapi_diff, repo_root=args.repo_root) or diff or "No OpenAPI diff artifact supplied."
        consumers = read_text(args.consumer_list, repo_root=args.repo_root) or "No consumer-list artifact supplied."
        evidence = common + [
            evidence_object("openapi-diff", f"OpenAPI diff excerpt:\n{openapi_diff}"),
            evidence_object("consumer-list", f"Consumer list excerpt:\n{consumers}"),
            evidence_object("test-output", f"Contract test output excerpt:\n{test_output}"),
        ]
        candidate = (
            "Review this API contract change before merge or release. "
            f"OpenAPI diff: {openapi_diff}. Consumers: {consumers}. Tests: {test_output}."
        )
        return {
            "adapter": adapter_id,
            "request": "Check API contract change compatibility, versioning, docs, tests, and consumer impact.",
            "candidate": candidate,
            "evidence": evidence,
            "constraints": [
                "Verify breaking changes, versioning, docs, tests, and impacted consumers.",
            ],
        }

    if adapter_id == "infrastructure_change_guardrail":
        iac_plan = read_text(args.iac_plan, repo_root=args.repo_root) or diff or "No IaC plan artifact supplied."
        evidence = common + [evidence_object("iac-plan-output", f"IaC plan/diff excerpt:\n{iac_plan}")]
        candidate = (
            "Review this infrastructure change before apply or merge. "
            f"IaC plan/diff: {iac_plan}. CI status: {ci_status}."
        )
        return {
            "adapter": adapter_id,
            "request": "Check infrastructure change blast radius, secrets, rollback, cost, region, and compliance.",
            "candidate": candidate,
            "evidence": evidence,
            "constraints": [
                "Verify blast radius, secrets/security, rollback, cost, region, and compliance before apply.",
            ],
        }

    if adapter_id == "database_migration_guardrail":
        migration_diff = read_text(args.migration_diff, repo_root=args.repo_root) or diff or "No migration diff artifact supplied."
        schema_state = read_text(args.schema_state, repo_root=args.repo_root) or "No schema-state artifact supplied."
        backup_status = read_text(args.backup_status, repo_root=args.repo_root) or "No backup-status artifact supplied."
        rollout_plan = read_text(args.rollout_plan, repo_root=args.repo_root) or "No rollout-plan artifact supplied."
        evidence = common + [
            evidence_object("migration-diff", f"Migration diff excerpt:\n{migration_diff}"),
            evidence_object("schema-state", f"Schema state excerpt:\n{schema_state}"),
            evidence_object("backup-status", f"Backup status excerpt:\n{backup_status}"),
            evidence_object("rollout-plan", f"Rollout plan excerpt:\n{rollout_plan}"),
        ]
        candidate = (
            "Review this database migration before execution, merge, or rollout. "
            f"Migration diff: {migration_diff}. Schema state: {schema_state}. "
            f"Backup status: {backup_status}. Rollout plan: {rollout_plan}."
        )
        return {
            "adapter": adapter_id,
            "request": "Check database migration data loss, locks, rollback, backfill, compatibility, and backup.",
            "candidate": candidate,
            "evidence": evidence,
            "constraints": [
                "Verify data loss, locks, rollback, backfill, compatibility, and backup before migration.",
            ],
        }
    raise GitHubGuardrailError(f"Unsupported adapter: {adapter_id}")


def should_fail(result, fail_on):
    if fail_on == "never":
        return False
    if fail_on == "gate-fail":
        return result.get("gate_decision") != "pass"
    if fail_on == "recommended-action":
        return result.get("gate_decision") != "pass" or result.get("recommended_action") != "accept"
    if fail_on == "candidate-block":
        return result.get("gate_decision") != "pass" or result.get("candidate_gate") == "block"
    raise GitHubGuardrailError(f"Unsupported fail-on mode: {fail_on}")


def prepare_outputs(output_dir, append=False):
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_log = output_dir / "audit.jsonl"
    if append:
        audit_log.touch(exist_ok=True)
    else:
        audit_log.write_text("", encoding="utf-8")
    return {
        "output_dir": output_dir,
        "audit_log": audit_log,
        "metrics": output_dir / "metrics.json",
        "report_json": output_dir / "report.json",
        "summary_md": output_dir / "summary.md",
    }


def write_json(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def render_markdown(report):
    lines = [
        "# AANA GitHub Guardrails",
        "",
        f"Status: {'PASS' if report['valid'] else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Checked adapters: {report['summary']['checked']}",
        f"- Skipped adapters: {report['summary']['skipped']}",
        f"- Failing adapters: {report['summary']['failed']}",
        f"- Fail mode: `{report['fail_on']}`",
        f"- Audit log: `{report['audit_log']}`",
        f"- Metrics JSON: `{report['metrics_output']}`",
        "",
        "| Adapter | Status | Gate | Action | Candidate Gate | AIx | Candidate AIx | Violations |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["adapters"]:
        lines.append(
            "| {adapter} | {status} | {gate} | {action} | {candidate_gate} | {aix} | {candidate_aix} | {violations} |".format(
                adapter=item["adapter_id"],
                status=item["status"],
                gate=item.get("gate_decision", ""),
                action=item.get("recommended_action", ""),
                candidate_gate=item.get("candidate_gate", ""),
                aix=item.get("aix_decision", ""),
                candidate_aix=item.get("candidate_aix_decision", ""),
                violations=", ".join(item.get("violations", [])),
            )
        )
    return "\n".join(lines) + "\n"


def adapter_report(adapter_id, workflow, result, failed):
    aix = result.get("aix", {}) if isinstance(result.get("aix"), dict) else {}
    candidate_aix = result.get("candidate_aix", {}) if isinstance(result.get("candidate_aix"), dict) else {}
    return {
        "adapter_id": adapter_id,
        "status": "fail" if failed else "pass",
        "workflow_id": workflow.get("workflow_id"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "candidate_aix_score": candidate_aix.get("score"),
        "candidate_aix_decision": candidate_aix.get("decision"),
        "violations": [violation.get("code") for violation in result.get("violations", [])],
        "safe_response": result.get("output"),
    }


def run_guardrails(args):
    repo_root = pathlib.Path(args.repo_root).resolve()
    if not repo_root.exists():
        raise GitHubGuardrailError(f"Repository root does not exist: {repo_root}")
    outputs = prepare_outputs(args.output_dir, append=args.append)
    files = changed_files(repo_root, base_ref=args.base_ref, head_ref=args.head_ref, explicit=args.changed_files)
    diff = diff_text(repo_root, base_ref=args.base_ref, head_ref=args.head_ref, diff_file=args.diff_file)

    adapters = split_values(args.adapters) or list(DEFAULT_ADAPTERS)
    reports = []
    checked_results = []
    for adapter_id in adapters:
        if adapter_id not in DEFAULT_ADAPTERS:
            raise GitHubGuardrailError(f"Unsupported GitHub guardrail adapter: {adapter_id}")
        if not adapter_relevant(adapter_id, files, args):
            reports.append({"adapter_id": adapter_id, "status": "skipped", "reason": "No relevant evidence or changed files detected."})
            continue
        check = build_check(adapter_id, files, diff, args)
        workflow = agent_api.check_workflow(
            adapter=check["adapter"],
            request=check["request"],
            candidate=check["candidate"],
            evidence=check["evidence"],
            constraints=check["constraints"],
            allowed_actions=DEFAULT_ALLOWED_ACTIONS,
            metadata={
                "surface": "github_action",
                "github_event_name": os.getenv("GITHUB_EVENT_NAME"),
                "github_workflow": os.getenv("GITHUB_WORKFLOW"),
                "github_repository": os.getenv("GITHUB_REPOSITORY"),
                "github_sha": os.getenv("GITHUB_SHA"),
                "changed_files_count": len(files),
            },
            workflow_id=f"github-{adapter_id}",
            gallery_path=args.gallery,
        )
        agent_api.append_audit_record(outputs["audit_log"], agent_api.audit_workflow_check({
            "contract_version": agent_api.WORKFLOW_CONTRACT_VERSION,
            "workflow_id": f"github-{adapter_id}",
            "adapter": check["adapter"],
            "request": check["request"],
            "candidate": check["candidate"],
            "evidence": check["evidence"],
            "constraints": check["constraints"],
            "allowed_actions": DEFAULT_ALLOWED_ACTIONS,
            "metadata": {"surface": "github_action", "changed_files_count": len(files)},
        }, workflow))
        failed = should_fail(workflow, args.fail_on)
        reports.append(adapter_report(adapter_id, {"workflow_id": f"github-{adapter_id}"}, workflow, failed))
        checked_results.append(workflow)

    metrics = agent_api.export_audit_metrics_file(outputs["audit_log"], output_path=outputs["metrics"])
    failed_reports = [item for item in reports if item.get("status") == "fail"]
    skipped_reports = [item for item in reports if item.get("status") == "skipped"]
    report = {
        "github_guardrails_report_version": "0.1",
        "valid": not failed_reports,
        "fail_on": args.fail_on,
        "repo_root": str(repo_root),
        "changed_files": files,
        "summary": {
            "adapters": len(reports),
            "checked": len(reports) - len(skipped_reports),
            "skipped": len(skipped_reports),
            "failed": len(failed_reports),
            "audit_records": metrics["record_count"],
        },
        "audit_log": str(outputs["audit_log"]),
        "metrics_output": str(outputs["metrics"]),
        "summary_markdown": str(outputs["summary_md"]),
        "adapters": reports,
        "metrics": metrics,
    }
    write_json(outputs["report_json"], report)
    summary_md = render_markdown(report)
    outputs["summary_md"].write_text(summary_md, encoding="utf-8")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with pathlib.Path(step_summary).open("a", encoding="utf-8") as handle:
            handle.write(summary_md)
            handle.write("\n")
    for item in failed_reports:
        print(f"::error title=AANA {item['adapter_id']} guardrail failed::{item.get('violations', [])}")
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AANA GitHub Action guardrails.")
    parser.add_argument("--repo-root", default=os.getenv("GITHUB_WORKSPACE", "."), help="Repository workspace to inspect.")
    parser.add_argument("--gallery", default=ROOT / "examples" / "adapter_gallery.json", help="AANA adapter gallery JSON.")
    parser.add_argument("--adapters", default=",".join(DEFAULT_ADAPTERS), help="Comma/newline separated adapter ids.")
    parser.add_argument("--fail-on", default="candidate-block", choices=["never", "gate-fail", "recommended-action", "candidate-block"])
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for audit, metrics, and reports.")
    parser.add_argument("--append", action="store_true", help="Append to existing audit log.")
    parser.add_argument("--force", action="store_true", help="Run all selected adapters even if no relevant files are detected.")
    parser.add_argument("--base-ref", default=os.getenv("GITHUB_BASE_REF") or os.getenv("AANA_BASE_REF"))
    parser.add_argument("--head-ref", default=os.getenv("GITHUB_SHA") or os.getenv("AANA_HEAD_REF"))
    parser.add_argument("--changed-files", default=None, help="Explicit comma/newline separated changed files.")
    parser.add_argument("--diff-file", default=None, help="Path to a checked-out diff artifact.")
    parser.add_argument("--test-output", default=None, help="Path to test output artifact.")
    parser.add_argument("--ci-status", default=None, help="CI status summary.")
    parser.add_argument("--deployment-manifest", default=None, help="Path to deployment manifest evidence.")
    parser.add_argument("--release-notes", default=None, help="Path to release notes evidence.")
    parser.add_argument("--openapi-diff", default=None, help="Path to OpenAPI diff evidence.")
    parser.add_argument("--consumer-list", default=None, help="Path to API consumer-list evidence.")
    parser.add_argument("--iac-plan", default=None, help="Path to IaC plan or policy output evidence.")
    parser.add_argument("--migration-diff", default=None, help="Path to database migration diff evidence.")
    parser.add_argument("--schema-state", default=None, help="Path to database schema-state evidence.")
    parser.add_argument("--backup-status", default=None, help="Path to database backup-status evidence.")
    parser.add_argument("--rollout-plan", default=None, help="Path to database rollout-plan evidence.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)
    args.base_ref = args.base_ref or os.getenv("GITHUB_BASE_REF") or os.getenv("AANA_BASE_REF")
    args.head_ref = args.head_ref or os.getenv("GITHUB_SHA") or os.getenv("AANA_HEAD_REF")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        report = run_guardrails(args)
    except (GitHubGuardrailError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA GitHub guardrails: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["valid"] else "FAIL"
        print(f"AANA GitHub guardrails: {status}")
        print(f"- Checked adapters: {report['summary']['checked']}")
        print(f"- Skipped adapters: {report['summary']['skipped']}")
        print(f"- Failing adapters: {report['summary']['failed']}")
        print(f"- Audit log: {report['audit_log']}")
        print(f"- Metrics JSON: {report['metrics_output']}")
        print(f"- Summary: {report['summary_markdown']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
