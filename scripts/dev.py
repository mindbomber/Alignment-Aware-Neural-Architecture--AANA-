"""Small cross-platform helper commands for local development.

Usage:
    python scripts/dev.py test
    python scripts/dev.py sample
    python scripts/dev.py dry-run
    python scripts/dev.py check
    python scripts/dev.py production-profiles
    python scripts/dev.py production-profiles --audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl --metrics-output eval_outputs/audit/ci/aana-ci-metrics.json
    python scripts/dev.py contract-freeze
    python scripts/dev.py pilot-certify
    python scripts/dev.py pilot-bundle
    python scripts/dev.py pilot-eval
    python scripts/dev.py starter-kits
    python scripts/dev.py design-partner-pilots
    python scripts/dev.py github-guardrails
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile


PYTHON = sys.executable


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def compile_python():
    run([PYTHON, "-m", "compileall", "eval_pipeline", "tests", "scripts"])


def test():
    run([PYTHON, "-m", "unittest", "discover", "-s", "tests"])


def sample():
    run(
        [
            PYTHON,
            "eval_pipeline/score_outputs.py",
            "--input",
            "examples/sample_raw_outputs.jsonl",
            "--scored",
            "examples/sample_scored_outputs.csv",
            "--summary",
            "examples/sample_summary_by_condition.csv",
        ]
    )


def dry_run():
    run(
        [
            PYTHON,
            "eval_pipeline/generate_heldout_tasks.py",
            "--output",
            "eval_outputs/heldout/heldout_ats_aana_tasks.jsonl",
        ]
    )
    run(
        [
            PYTHON,
            "eval_pipeline/run_evals.py",
            "--limit",
            "2",
            "--dry-run",
            "--no-resume",
            "--output",
            "eval_outputs/raw_outputs.jsonl",
        ]
    )
    run(
        [
            PYTHON,
            "eval_pipeline/score_outputs.py",
            "--input",
            "eval_outputs/raw_outputs.jsonl",
            "--scored",
            "eval_outputs/scored_outputs.csv",
            "--summary",
            "eval_outputs/summary_by_condition.csv",
        ]
    )


def check():
    compile_python()
    test()
    sample()


def contract_freeze():
    run([PYTHON, "scripts/aana_cli.py", "contract-freeze"])


def pilot_certify():
    run([PYTHON, "scripts/aana_cli.py", "pilot-certify"])


def production_profiles(audit_log=None, metrics_output=None, drift_output=None, reviewer_report_output=None, manifest_output=None):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        audit_log_path = pathlib.Path(audit_log) if audit_log else temp_path / "aana-ci-audit.jsonl"
        metrics_output_path = pathlib.Path(metrics_output) if metrics_output else temp_path / "aana-ci-metrics.json"
        drift_output_path = pathlib.Path(drift_output) if drift_output else audit_log_path.parent / "aana-ci-aix-drift.json"
        reviewer_report_path = pathlib.Path(reviewer_report_output) if reviewer_report_output else audit_log_path.parent / "aana-ci-reviewer-report.md"
        manifest_path = pathlib.Path(manifest_output) if manifest_output else audit_log_path.parent / "manifests" / "aana-ci-audit-integrity.json"
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_output_path.parent.mkdir(parents=True, exist_ok=True)
        drift_output_path.parent.mkdir(parents=True, exist_ok=True)
        reviewer_report_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        audit_log_path.write_text("", encoding="utf-8")
        run([PYTHON, "scripts/aana_cli.py", "validate-gallery", "--run-examples"])
        run([PYTHON, "scripts/aana_cli.py", "pilot-certify"])
        run([PYTHON, "scripts/aana_cli.py", "contract-freeze", "--evidence-registry", "examples/evidence_registry.json"])
        run([PYTHON, "scripts/aana_cli.py", "aix-tuning"])
        run([PYTHON, "scripts/aana_cli.py", "validate-deployment", "--deployment-manifest", "examples/production_deployment_internal_pilot.json"])
        run([PYTHON, "scripts/aana_cli.py", "validate-governance", "--governance-policy", "examples/human_governance_policy_internal_pilot.json"])
        run([PYTHON, "scripts/aana_cli.py", "validate-observability", "--observability-policy", "examples/observability_policy_internal_pilot.json"])
        run([PYTHON, "scripts/aana_cli.py", "validate-evidence-registry", "--evidence-registry", "examples/evidence_registry.json"])
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "evidence-integrations",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--mock-fixtures",
                "examples/evidence_mock_connector_fixtures.json",
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "agent-check",
                "--event",
                "examples/agent_event_support_reply.json",
                "--audit-log",
                str(audit_log_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "audit-validate",
                "--audit-log",
                str(audit_log_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "audit-metrics",
                "--audit-log",
                str(audit_log_path),
                "--output",
                str(metrics_output_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "audit-drift",
                "--audit-log",
                str(audit_log_path),
                "--output",
                str(drift_output_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "audit-manifest",
                "--audit-log",
                str(audit_log_path),
                "--output",
                str(manifest_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "audit-reviewer-report",
                "--audit-log",
                str(audit_log_path),
                "--metrics",
                str(metrics_output_path),
                "--drift-report",
                str(drift_output_path),
                "--manifest",
                str(manifest_path),
                "--output",
                str(reviewer_report_path),
            ]
        )
        run(
            [
                PYTHON,
                "scripts/aana_cli.py",
                "release-check",
                "--skip-local-check",
                "--deployment-manifest",
                "examples/production_deployment_internal_pilot.json",
                "--governance-policy",
                "examples/human_governance_policy_internal_pilot.json",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--observability-policy",
                "examples/observability_policy_internal_pilot.json",
                "--audit-log",
                str(audit_log_path),
            ]
        )


def pilot_bundle():
    run([PYTHON, "scripts/run_e2e_pilot_bundle.py"])


def pilot_eval():
    run([PYTHON, "scripts/run_pilot_evaluation_kit.py"])


def starter_kits():
    run([PYTHON, "scripts/run_starter_pilot_kit.py", "--kit", "all"])


def design_partner_pilots():
    run([PYTHON, "scripts/run_design_partner_pilots.py", "--pilot", "all"])


def github_guardrails():
    run([PYTHON, "scripts/run_github_action_guardrails.py", "--force", "--fail-on", "never"])


COMMANDS = {
    "compile": compile_python,
    "test": test,
    "sample": sample,
    "dry-run": dry_run,
    "check": check,
    "contract-freeze": contract_freeze,
    "pilot-certify": pilot_certify,
    "pilot-bundle": pilot_bundle,
    "pilot-eval": pilot_eval,
    "starter-kits": starter_kits,
    "design-partner-pilots": design_partner_pilots,
    "github-guardrails": github_guardrails,
    "production-profiles": production_profiles,
}


def main():
    parser = argparse.ArgumentParser(description="Run common local development commands.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--audit-log", default=None, help="Production-profiles audit JSONL artifact path.")
    parser.add_argument("--metrics-output", default=None, help="Production-profiles audit metrics JSON artifact path.")
    parser.add_argument("--drift-output", default=None, help="Production-profiles AIx drift report JSON artifact path.")
    parser.add_argument("--reviewer-report-output", default=None, help="Production-profiles Markdown reviewer report artifact path.")
    parser.add_argument("--manifest-output", default=None, help="Production-profiles audit integrity manifest artifact path.")
    args = parser.parse_args()
    if args.command == "production-profiles":
        production_profiles(
            audit_log=args.audit_log,
            metrics_output=args.metrics_output,
            drift_output=args.drift_output,
            reviewer_report_output=args.reviewer_report_output,
            manifest_output=args.manifest_output,
        )
        return
    if args.audit_log or args.metrics_output or args.drift_output or args.reviewer_report_output or args.manifest_output:
        parser.error("--audit-log, --metrics-output, --drift-output, --reviewer-report-output, and --manifest-output are only supported for production-profiles.")
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
