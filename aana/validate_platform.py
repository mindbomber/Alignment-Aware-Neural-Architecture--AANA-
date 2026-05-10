#!/usr/bin/env python
"""Validate that the AANA platform surfaces are wired together coherently."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import subprocess
import sys
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@dataclasses.dataclass(frozen=True)
class PlatformGate:
    name: str
    category: str
    command: list[str]
    description: str


def platform_gates(*, require_existing_artifacts: bool = True, include_agent_integrations: bool = True) -> list[PlatformGate]:
    artifact_flag = ["--require-existing-artifacts"] if require_existing_artifacts else []
    gates = [
        PlatformGate(
            "adapter_layout",
            "architecture",
            [PYTHON, "scripts/validation/validate_adapter_layout.py", "--json"],
            "Validate adapter-family manifests, product-bundle manifests, aliases, split isolation, and held-out coverage declarations.",
        ),
        PlatformGate(
            "bundle_certification",
            "bundles",
            [PYTHON, "scripts/validation/validate_bundle_certification.py", "--json"],
            "Validate enterprise, personal productivity, and government/civic bundle certification gates.",
        ),
        PlatformGate(
            "canonical_ids",
            "architecture",
            [PYTHON, "scripts/validation/validate_canonical_ids.py", "--json"],
            "Validate one canonical ID source for adapter families, bundles, routes, evidence types, runtime modes, and aliases.",
        ),
        PlatformGate(
            "registry",
            "architecture",
            [PYTHON, "scripts/validation/validate_registry.py", "--json"],
            "Validate the single AANA registry for adapters, bundles, datasets, evidence connectors, routes, and aliases.",
        ),
        PlatformGate(
            "repo_organization",
            "architecture",
            [PYTHON, "scripts/validation/validate_repo_organization.py", "--json"],
            "Validate canonical repository layout, grouped script boundaries, public path names, and alias containment.",
        ),
        PlatformGate(
            "contract_freeze",
            "contracts",
            [PYTHON, "scripts/aana_cli.py", "contract-freeze", "--evidence-registry", "examples/evidence_registry.json"],
            "Validate frozen Workflow Contract, Agent Event, evidence, audit, AIx, and schema compatibility boundaries.",
        ),
        PlatformGate(
            "hf_dataset_registry",
            "data",
            [PYTHON, "scripts/hf/validate_hf_dataset_registry.py"],
            "Validate HF dataset registry split-use isolation for calibration, held-out validation, and external reporting.",
        ),
        PlatformGate(
            "hf_calibration",
            "data",
            [PYTHON, "scripts/hf/validate_hf_calibration.py"],
            "Validate calibration families, metric tracking, and calibration/reporting split isolation.",
        ),
        PlatformGate(
            "hf_dataset_proof",
            "data",
            [PYTHON, "scripts/hf/validate_hf_dataset_proof.py", *artifact_flag],
            "Validate public HF dataset proof artifacts and measured adapter-family evidence boundaries.",
        ),
        PlatformGate(
            "privacy_pii_adapter_eval",
            "adapters",
            [PYTHON, "scripts/evals/run_privacy_pii_adapter_eval.py"],
            "Validate Privacy/PII adapter metrics from registered HF-derived validation cases.",
        ),
        PlatformGate(
            "grounded_qa_adapter_eval",
            "adapters",
            [PYTHON, "scripts/evals/run_grounded_qa_adapter_eval.py"],
            "Validate grounded-QA and hallucination adapter metrics from registered HF-derived validation cases.",
        ),
        PlatformGate(
            "agent_tool_use_control_eval",
            "adapters",
            [PYTHON, "scripts/evals/run_agent_tool_use_control_eval.py"],
            "Validate agent tool-use control metrics from registered HF-derived validation cases.",
        ),
        PlatformGate(
            "adapter_generalization",
            "adapters",
            [PYTHON, "scripts/validation/validate_adapter_generalization.py", *artifact_flag],
            "Validate benchmark-fit linting, held-out validation requirements, config-backed hints, and public-claim separation.",
        ),
        PlatformGate(
            "benchmark_fit_lint",
            "adapters",
            [PYTHON, "scripts/validation/validate_benchmark_fit_lint.py"],
            "Reject probe-style or answer-key-style benchmark fitting in general AANA paths.",
        ),
        PlatformGate(
            "public_claims_policy",
            "claims",
            [PYTHON, "scripts/validation/validate_public_claims_policy.py"],
            "Ensure public claims use the standard AANA claim and never merge probe/diagnostic results into public claims.",
        ),
        PlatformGate(
            "evidence_artifacts",
            "claims",
            [PYTHON, "scripts/validation/validate_evidence_artifacts.py"],
            "Validate reviewed evidence artifact labels, source splits, reproduction commands, and public-claim eligibility.",
        ),
        PlatformGate(
            "cross_domain_adapter_families",
            "adapters",
            [PYTHON, "scripts/validation/validate_cross_domain_adapter_families.py", *artifact_flag],
            "Validate external HF held-out coverage for cross-domain adapter families before stronger claims.",
        ),
        PlatformGate(
            "production_candidate_evidence_pack",
            "claims",
            [PYTHON, "scripts/validation/validate_production_candidate_evidence_pack.py", *artifact_flag],
            "Validate the public boundary: production-candidate audit/control layer, not proven raw agent-performance engine.",
        ),
        PlatformGate(
            "standard_publication",
            "publication",
            [PYTHON, "scripts/validation/validate_aana_standard_publication.py", *artifact_flag],
            "Validate publication readiness across Python package, TypeScript SDK, FastAPI service, cards, docs, and contract standard.",
        ),
        PlatformGate(
            "security_hardening",
            "security",
            [PYTHON, "scripts/validation/validate_security_hardening.py"],
            "Validate secret scanning, safe demo defaults, dependency audit wiring, and malicious-agent threat-model coverage.",
        ),
        PlatformGate(
            "packaging_hardening",
            "packaging",
            [PYTHON, "scripts/validation/validate_packaging_hardening.py", *artifact_flag],
            "Validate package/service/eval/docs separation and release checklist boundaries.",
        ),
        PlatformGate(
            "no_tracked_eval_outputs",
            "packaging",
            [PYTHON, "scripts/validation/validate_no_tracked_eval_outputs.py"],
            "Ensure generated eval_outputs files are not tracked in Git; reviewed evidence belongs under docs/evidence/peer_review.",
        ),
        PlatformGate(
            "versioning_migration",
            "contracts",
            [PYTHON, "scripts/validation/validate_versioning_migration.py"],
            "Validate public versioned surfaces, backward-compatible migration policy, and compatibility-test coverage.",
        ),
    ]
    if include_agent_integrations:
        gates.insert(
            4,
            PlatformGate(
                "agent_integrations",
                "integrations",
                [PYTHON, "scripts/validation/validate_agent_integrations.py", "--json"],
                "Validate Python SDK, TypeScript SDK, OpenAI Agents SDK, LangChain, AutoGen, CrewAI, FastAPI, MCP, and controlled-agent eval harness.",
            ),
        )
    gates.insert(
        5 if include_agent_integrations else 4,
        PlatformGate(
            "agent_contract_chaos",
            "integrations",
            [PYTHON, "scripts/validation/validate_agent_contract_chaos.py", "--json"],
            "Validate fail-closed behavior for malformed evidence, unknown tools, stale auth, contradictory evidence, oversized FastAPI payloads, mislabeled private reads, and bad runtime accept routes.",
        ),
    )
    return gates


def run_gate(gate: PlatformGate, *, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            gate.command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": gate.name,
            "category": gate.category,
            "description": gate.description,
            "command": gate.command,
            "valid": False,
            "returncode": None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": (exc.stdout or "")[-8000:],
            "stderr": f"Timed out after {timeout}s.\n{(exc.stderr or '')[-7900:]}",
        }
    return {
        "name": gate.name,
        "category": gate.category,
        "description": gate.description,
        "command": gate.command,
        "valid": completed.returncode == 0,
        "returncode": completed.returncode,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    }


def validate_platform(
    *,
    require_existing_artifacts: bool = True,
    include_agent_integrations: bool = True,
    fail_fast: bool = False,
    timeout: int = 240,
) -> dict[str, Any]:
    checks = []
    for gate in platform_gates(
        require_existing_artifacts=require_existing_artifacts,
        include_agent_integrations=include_agent_integrations,
    ):
        result = run_gate(gate, timeout=timeout)
        checks.append(result)
        if fail_fast and not result["valid"]:
            break
    return {
        "valid": all(check["valid"] for check in checks),
        "passed": sum(1 for check in checks if check["valid"]),
        "total": len(checks),
        "checks": checks,
    }


def _print_text_summary(report: dict[str, Any]) -> None:
    status = "pass" if report["valid"] else "block"
    print(f"{status} -- passed={report['passed']}/{report['total']}")
    for check in report["checks"]:
        check_status = "pass" if check["valid"] else "block"
        print(f"- {check_status}: {check['name']} [{check['category']}] {check['latency_ms']}ms")
        if not check["valid"]:
            print(f"  command: {' '.join(check['command'])}")
            if check.get("stderr"):
                print(f"  stderr: {check['stderr'].strip()[-1000:]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed gate.")
    parser.add_argument("--timeout", type=int, default=240, help="Per-gate timeout in seconds.")
    parser.add_argument(
        "--no-require-existing-artifacts",
        action="store_true",
        help="Do not pass --require-existing-artifacts to gates that support it.",
    )
    parser.add_argument(
        "--skip-agent-integrations",
        action="store_true",
        help="Skip the slower live integration smoke gate.",
    )
    args = parser.parse_args(argv)

    report = validate_platform(
        require_existing_artifacts=not args.no_require_existing_artifacts,
        include_agent_integrations=not args.skip_agent_integrations,
        fail_fast=args.fail_fast,
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text_summary(report)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
